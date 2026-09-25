# FolderWatcher

A macOS-oriented automation utility that watches a directory for CSV files, validates them, and converts stable files to JSON automatically.

FolderWatcher combines file polling, validation, configurable paths, rotating logs, error recovery, and optional background execution through `launchd`.

## Features

- continuously watches a source directory for CSV files;
- waits for a file to remain unchanged before processing it;
- validates CSV structure and required fields;
- converts valid CSV files to formatted JSON;
- preserves source CSV files;
- never overwrites an existing JSON result;
- retries a previously invalid CSV after the file changes;
- logs successful conversions, warnings, and errors;
- rotates the main log at approximately 1 MB;
- supports configurable source, output, log, polling, and settle settings;
- can run in the background with a macOS LaunchAgent;
- uses only the Python standard library.

## Requirements

- macOS
- Python 3.9+
- read access to source files
- write access to output and log locations
- no third-party Python dependencies

## Installation

```bash
git clone https://github.com/mihalkovskiisan-hash/FolderWatcher.git
cd FolderWatcher
python3 --version
```

## Quick start

Run:

```bash
python3 watcher.py
```

On first launch, the default configuration creates:

```text
source/
output/
watcher.log
```

Leave the process running and place a CSV file in `source/`. After the file remains unchanged for the configured settle period, a matching JSON file is written to `output/`.

Stop the watcher with `Ctrl+C`.

## Example

Input:

```csv
name,email,active
Anna,anna@example.com,yes
Ivan,ivan@example.com,no
```

Output:

```json
[
  {
    "name": "Anna",
    "email": "anna@example.com",
    "active": "yes"
  },
  {
    "name": "Ivan",
    "email": "ivan@example.com",
    "active": "no"
  }
]
```

## Configuration

Edit `config.json` before starting the watcher:

```json
{
  "source_folder": "source",
  "output_folder": "output",
  "log_file": "watcher.log",
  "poll_interval_seconds": 2,
  "settle_seconds": 5
}
```

| Setting | Purpose |
| --- | --- |
| `source_folder` | Directory containing incoming CSV files |
| `output_folder` | Directory for generated JSON files |
| `log_file` | Main application log |
| `poll_interval_seconds` | Delay between directory scans |
| `settle_seconds` | Required unchanged period before processing |

Relative paths are resolved from the directory containing `config.json`. Absolute paths and paths containing `~` are also supported.

The source and output directories must be separate and must not be nested inside one another.

## CSV validation

CSV files are read as UTF-8, including UTF-8 with BOM.

Each file must:

- contain non-empty, unique column names;
- contain the required columns `name`, `email`, and `active`;
- contain non-empty values for required fields;
- contain at least one data row;
- contain the same number of values as headers.

Additional columns are preserved. Values remain strings.

## Processing model

FolderWatcher polls the source directory and tracks each file by inode, size, and modification time.

A new or changed CSV is processed only after it remains unchanged for `settle_seconds`. This reduces the chance of reading a file while another process is still writing it.

For a more reliable handoff, write the incoming file under a temporary extension first and rename it to `.csv` only after writing is complete.

Hidden files, nested directories, symbolic links, and non-CSV files are ignored.

## Error handling

An invalid CSV is logged as an error without stopping the watcher.

After the file changes, the new version becomes eligible for processing again.

If the destination JSON already exists, the conversion is skipped rather than overwriting it.

## Logging

Each log record contains a timestamp, level, and message.

The main `watcher.log` rotates at approximately 1 MB and keeps up to three backups:

```text
watcher.log
watcher.log.1
watcher.log.2
watcher.log.3
```

## Running with launchd

The repository includes `local.folderwatcher.plist` as a LaunchAgent template for running FolderWatcher in the background.

Before installing it, replace `YOUR_USERNAME` with your macOS account name and verify the Python executable path:

```bash
command -v python3
python3 --version
```

Then validate and install the plist:

```bash
plutil -lint local.folderwatcher.plist
mkdir -p ~/Library/LaunchAgents
cp local.folderwatcher.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/local.folderwatcher.plist
launchctl print gui/$(id -u)/local.folderwatcher
```

To unload it:

```bash
launchctl bootout gui/$(id -u)/local.folderwatcher
```

If you modify the plist, unload the existing agent, copy the updated plist into `~/Library/LaunchAgents`, and bootstrap it again.

## Project structure

| File | Purpose |
| --- | --- |
| `watcher.py` | Configuration, polling, state tracking, logging, and process loop |
| `converter.py` | CSV validation and CSV-to-JSON conversion |
| `config.json` | Runtime settings |
| `local.folderwatcher.plist` | macOS LaunchAgent template |
| `README.md` | Documentation |

## Current limitations

- only CSV files directly inside the source directory are processed;
- polling is used instead of native filesystem events;
- the settle period reduces but cannot eliminate partial-write races;
- source CSV files are loaded fully into memory;
- output JSON files are never overwritten automatically;
- removing an output JSON while the watcher is still running does not by itself trigger reprocessing;
- only one watcher instance should manage a given source/output pair;
- interrupted writes may leave a partial JSON file;
- `launchd.stdout.log` and `launchd.stderr.log` are not rotated automatically.
