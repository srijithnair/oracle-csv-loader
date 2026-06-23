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
- `tkinter` for the interactive file picker (included with most Python installs on macOS and Windows)

### Windows

```powershell
git clone https://github.com/srijithnair/oracle-csv-loader.git
cd oracle-csv-loader
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Use paths like `C:\Users\you\data` when prompted. Install Python from [python.org](https://www.python.org/downloads/) (not the Microsoft Store build) to ensure `tkinter` is included. If the file picker is unavailable, use `csv_to_oracle_loader.py` instead.

**No Grok or xAI account is required** — this is a standalone Python CLI.

## Testing status

This project has **not** been verified end-to-end against a live Oracle database. The following has been tested locally:

| Area | Status |
|------|--------|
| Python syntax / imports | Pass |
| Connection string parsing | Pass |
| CSV schema inference + DDL generation | Pass |
| CSV read → row conversion | Pass |
| `tkinter` availability (macOS) | Pass |
| `oracledb` driver loads | Pass |

The following has **not** yet been tested:

- Connecting to a real Oracle 19c instance
- Running `CREATE TABLE` and confirming the schema
- Inserting rows and verifying them in the database
- The full interactive flow (`main.py` prompts + file picker)
- Windows
- Edge cases: passwords with `@`, very large CSVs, column name mismatches, existing-table mapping

To validate against your environment you will need an Oracle 19c database, a test CSV file, and credentials with `CREATE TABLE` and `INSERT` privileges.

## License

MIT License

---

Created with help from Grok. Feel free to open issues or submit pull requests!
