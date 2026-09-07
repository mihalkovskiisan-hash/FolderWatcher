import csv
import json
import math
import time
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from converter import convert_csv


def load_config(config_path: Path) -> dict:
    """Прочитать настройки, проверить значения и раскрыть пути."""
    config_path = config_path.resolve()
    with config_path.open(encoding="utf-8") as file:
        config = json.load(file)

    if not isinstance(config, dict):
        raise ValueError("Конфиг должен содержать JSON-объект")

    for key in ("source_folder", "output_folder", "log_file"):
        value = config.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key}: укажите непустой путь")

        path = Path(value).expanduser()
        if not path.is_absolute():
            path = config_path.parent / path
        config[key] = path.resolve()

    for key in ("poll_interval_seconds", "settle_seconds"):
        value = config.get(key)
        if (
            type(value) not in (int, float)
            or not math.isfinite(value)
            or value <= 0
        ):
            raise ValueError(f"{key}: укажите положительное конечное число")

    source = config["source_folder"]
    output = config["output_folder"]
    if source == output or source in output.parents or output in source.parents:
        raise ValueError("Папки source и output должны быть отдельными и не вложенными")

    return config



def prepare_folders(config: dict) -> None:
    """Создать рабочие папки, если их ещё нет."""
    config["source_folder"].mkdir(parents=True, exist_ok=True)
    config["output_folder"].mkdir(parents=True, exist_ok=True)
    config["log_file"].parent.mkdir(parents=True, exist_ok=True)


def setup_logging(log_path: Path) -> None:
    """Писать события в терминал и лог с ограничением размера."""
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[file_handler, logging.StreamHandler()],
        force=True,
    )


def process_folder(config: dict, pending: dict, attempted: dict) -> None:
    """Обработать новые версии CSV после периода без изменений."""
    try:
        files = sorted(config["source_folder"].iterdir())
    except OSError as error:
        logging.error("Не удалось прочитать папку source: %s", error)
        return

    # Удалённые файлы больше не нужно помнить.
    present = set(files)
    for state in (pending, attempted):
        for path in list(state):
            if path not in present:
                del state[path]

    for source in files:
        try:
            if source.name.startswith(".") or source.suffix.lower() != ".csv":
                continue
            if source.is_symlink() or not source.is_file():
                continue

            stat = source.stat()
            version = (stat.st_ino, stat.st_size, stat.st_mtime_ns)
            if attempted.get(source) == version:
                continue

            now = time.monotonic()
            previous = pending.get(source)
            if previous is None or previous[0] != version:
                pending[source] = (version, now)
                continue
            if now - previous[1] < config["settle_seconds"]:
                continue

            # Ошибочный CSV повторно проверим после его изменения.
            attempted[source] = version
            output = config["output_folder"] / source.with_suffix(".json").name
            count = convert_csv(source, output)
        except FileExistsError:
            logging.warning("Пропуск %s: результат уже существует", source.name)
        except (OSError, ValueError, csv.Error) as error:
            logging.error("Ошибка обработки %s: %s", source.name, error)
        else:
            logging.info("%s → %s: записей %s", source.name, output.name, count)


def watch(config: dict) -> None:
    """Проверять папку до нажатия Ctrl+C."""
    pending = {}
    attempted = {}
    logging.info("Наблюдение запущено. Для остановки нажмите Ctrl+C")
    try:
        while True:
            process_folder(config, pending, attempted)
            time.sleep(config["poll_interval_seconds"])
    except KeyboardInterrupt:
        logging.info("Наблюдение остановлено пользователем")


def main() -> None:
    config_path = Path(__file__).resolve().with_name("config.json")
    try:
        config = load_config(config_path)
    except (OSError, ValueError) as error:
        raise SystemExit(f"Ошибка конфигурации: {error}")

    try:
        prepare_folders(config)
        setup_logging(config["log_file"])
    except OSError as error:
        raise SystemExit(f"Не удалось подготовить папки или лог: {error}")

    logging.info("Рабочие папки готовы")
    logging.info("Источник CSV: %s", config["source_folder"])
    logging.info("Результаты JSON: %s", config["output_folder"])

    watch(config)


if __name__ == "__main__":
    main()
