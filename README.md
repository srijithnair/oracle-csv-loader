# Oracle CSV Loader

A robust Python CLI tool to load one or more CSV files into **Oracle Database** tables. Each table is automatically created (or reused) with the **same name as the source CSV file**.

## Features

- ✅ Interactive or CLI-driven multi-file selection (supports ranges like `1-5` and `all`)
- ✅ Automatic table creation with smart data type inference
  - `NUMBER` for integers/floats
  - `TIMESTAMP` for dates
  - `VARCHAR2` / `CLOB` for text
- ✅ Handles existing tables intelligently:
  - Append
  - Replace (TRUNCATE + INSERT)
  - Recreate (DROP + CREATE)
  - Skip
- ✅ Batched inserts (default 10,000 rows) for performance and low memory usage
- ✅ Works with Oracle 19c, 21c, 23ai (thin mode — no Oracle Instant Client required)
- ✅ Proper NULL handling and column name sanitization

## Installation

```bash
pip install oracledb pandas
```

## Quick Start (Interactive)

```bash
python csv_to_oracle_loader.py --dir /path/to/your/csvs
```

You will be prompted to:
1. Select which CSV files to load
2. Enter Oracle credentials and connection string
3. Choose action if tables already exist

## Command Line Examples

```bash
# Non-interactive append
python csv_to_oracle_loader.py \
  --dir ./data \
  --user MYDBUSER \
  --dsn "dbhost.example.com:1521/ORCLPDB1" \
  --if-exists append

# Replace (truncate) mode
python csv_to_oracle_loader.py --dir ./exports --if-exists replace --batch-size 20000

# Only create empty tables (no data load)
python csv_to_oracle_loader.py --dir ./data --create-only
```

## Connection String

Use Oracle Easy Connect syntax:

```
hostname:port/service_name
```

Example: `dbserver.company.com:1521/ORCLPDB1`

You can also set the password via environment variable:

```bash
export ORACLE_PASSWORD=your_secret_password
```

## Requirements

- Python 3.8+
- Oracle Database 12c or newer (tested on 19c)
- Privileges: `CREATE TABLE`, `INSERT`, `SELECT` on the target schema

## License

MIT License

---

Created with help from Grok. Feel free to open issues or submit pull requests!