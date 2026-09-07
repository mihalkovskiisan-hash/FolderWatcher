import csv
import json
from pathlib import Path


REQUIRED_FIELDS = {"name", "email", "active"}


def read_csv(source: Path) -> list[dict[str, str]]:
    """Прочитать CSV и вернуть проверенные записи."""
    with source.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file, strict=True)
        headers = reader.fieldnames

        if not headers:
            raise ValueError("CSV не содержит заголовков")

        if any(not header.strip() for header in headers):
            raise ValueError("В CSV есть столбец без названия")

        if len(headers) != len(set(headers)):
            raise ValueError("Названия столбцов CSV повторяются")

        missing = REQUIRED_FIELDS - set(headers)
        if missing:
            raise ValueError(
                "Отсутствуют обязательные столбцы: " + ", ".join(sorted(missing))
            )

        rows = []
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError(
                    f"Строка {reader.line_num}: число значений не совпадает с заголовками"
                )

            empty = [field for field in REQUIRED_FIELDS if not row[field].strip()]
            if empty:
                raise ValueError(
                    f"Строка {reader.line_num}: пустые обязательные поля: "
                    + ", ".join(sorted(empty))
                )

            rows.append(row)

        if not rows:
            raise ValueError("CSV не содержит строк с данными")

    return rows


def convert_csv(source: Path, output: Path) -> int:
    """Сохранить записи CSV в новый JSON и вернуть их количество."""
    rows = read_csv(source)
    content = json.dumps(rows, ensure_ascii=False, indent=2)

    with output.open("x", encoding="utf-8") as file:
        file.write(content + "\n")

    return len(rows)
