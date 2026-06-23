# Oracle CSV Loader

Python tools to load one or more CSV files into **Oracle Database 19c** tables with automatic schema inference and batched inserts.

## Tools

### Interactive loader (`main.py`) — recommended

A guided workflow that walks you through:

1. Choosing a directory path
2. Selecting multiple CSV files (native file picker)
3. Entering an Oracle connection string
4. Creating a new table (with schema preview + confirmation) or inserting into an existing table
5. Loading all selected CSVs into the target table

```bash
python main.py
```

**Connection string format:**

```
username/password@host:port/service_name
```

Example: `scott/tiger@localhost:1521/ORCLPDB1`

### CLI loader (`csv_to_oracle_loader.py`)

Batch-oriented script that creates one table per CSV file (table name = CSV filename). Supports append, replace, recreate, and skip modes.

```bash
python csv_to_oracle_loader.py --dir /path/to/your/csvs
```

See `csv_to_oracle_loader.py --help` for flags like `--if-exists`, `--batch-size`, and `--create-only`.

## Features

- Multi-file CSV selection
- Automatic Oracle type inference (`NUMBER`, `TIMESTAMP`, `VARCHAR2`, `CLOB`)
- Schema confirmation before `CREATE TABLE`
- Column mapping when inserting into existing tables
- Batched inserts for performance
- NULL handling and column name sanitization

## Installation

```bash
git clone https://github.com/srijithnair/oracle-csv-loader.git
cd oracle-csv-loader
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Project layout

```
oracle-csv-loader/
├── main.py                  # Interactive loader entry point
├── csv_to_oracle_loader.py  # CLI loader (one table per CSV)
├── requirements.txt
└── src/
    ├── prompts.py           # Interactive prompts and file picker
    ├── connection.py        # Oracle connection and DML
    ├── schema.py            # CSV type inference and DDL
    └── loader.py            # Interactive workflow orchestration
```

## Requirements

- Python 3.8+
- Oracle Database 12c or newer (tested on 19c)
- Privileges: `CREATE TABLE`, `INSERT`, `SELECT` on the target schema
- `tkinter` for the interactive file picker (included with most Python installs on macOS)

## License

MIT License

---

Created with help from Grok. Feel free to open issues or submit pull requests!
