#!/usr/bin/env python3
"""
Oracle 19c CSV Loader
=====================
- Prompts for a directory
- Lets you select multiple CSV files (supports 1,3,5 or 1-5 or 'all')
- Creates Oracle tables named after the CSV files (sanitized)
- Infers sensible column types (NUMBER, VARCHAR2, TIMESTAMP, CLOB)
- Handles existing tables (append / replace / recreate / skip)
- Uses batched inserts for performance
- Works with Oracle 19c (thin mode - no Oracle client required)

Install:
    pip install oracledb pandas

Usage examples:
    python csv_to_oracle_loader.py
    python csv_to_oracle_loader.py --dir ./data --if-exists append
    python csv_to_oracle_loader.py --dir ./exports --if-exists replace --batch-size 20000
"""

import os
import re
import argparse
import getpass
from datetime import datetime

import pandas as pd
import oracledb


def sanitize_identifier(name: str) -> str:
    """Convert any string into a valid Oracle identifier (uppercase)."""
    if not name or not str(name).strip():
        return "COL"
    name = re.sub(r'[^A-Za-z0-9_]', '_', str(name).strip())
    if name[0].isdigit():
        name = 'C_' + name
    return name.upper()[:128]


def optimize_dataframe_types(df: pd.DataFrame) -> pd.DataFrame:
    """Try to convert object columns to numeric or datetime where it makes sense."""
    for col in df.select_dtypes(include=['object']).columns:
        # Try numeric first
        numeric = pd.to_numeric(df[col], errors='coerce')
        if numeric.notna().sum() / len(df) > 0.85:
            df[col] = numeric
            continue

        # Try datetime
        try:
            dt = pd.to_datetime(df[col], errors='coerce', format='mixed')
            if dt.notna().sum() / len(df) > 0.75:
                df[col] = dt
        except Exception:
            pass
    return df


def get_oracle_type(series: pd.Series) -> str:
    """Map pandas dtype to Oracle type."""
    if pd.api.types.is_integer_dtype(series):
        return "NUMBER"
    elif pd.api.types.is_float_dtype(series):
        return "NUMBER"
    elif pd.api.types.is_datetime64_any_dtype(series):
        return "TIMESTAMP"
    elif pd.api.types.is_bool_dtype(series):
        return "NUMBER(1)"
    else:
        # String / object
        non_null = series.dropna().astype(str)
        if len(non_null) == 0:
            max_len = 255
        else:
            max_len = int(non_null.str.len().max() or 50)
        if max_len > 4000:
            return "CLOB"
        return f"VARCHAR2({max(50, max_len)})"


def table_exists(conn, table_name: str) -> bool:
    sql = """
        SELECT 1 FROM user_tables 
        WHERE table_name = :tab 
        FETCH FIRST 1 ROWS ONLY
    """
    with conn.cursor() as cur:
        cur.execute(sql, tab=table_name.upper())
        return cur.fetchone() is not None


def create_table(conn, table_name: str, df: pd.DataFrame):
    """Create table with inferred types."""
    cols = []
    for col in df.columns:
        clean = sanitize_identifier(col)
        ora_type = get_oracle_type(df[col])
        cols.append(f'"{clean}" {ora_type}')

    create_sql = f"""
        CREATE TABLE "{table_name}" (
            {',\n            '.join(cols)}
        )
    """
    with conn.cursor() as cur:
        cur.execute(create_sql)
    print(f"  ✓ Created table: {table_name}")


def handle_existing_table(conn, table_name: str, mode: str) -> str:
    """Decide what to do when table already exists."""
    if mode != 'prompt':
        return mode

    print(f"  Table '{table_name}' already exists.")
    while True:
        choice = input("  [A]ppend  |  [R]eplace (truncate)  |  [C]reate new (drop+recreate)  |  [S]kip: ").strip().upper()
        if choice in ('A', 'APPEND'):
            return 'append'
        elif choice in ('R', 'REPLACE'):
            return 'replace'
        elif choice in ('C', 'CREATE', 'RECREATE'):
            return 'recreate'
        elif choice in ('S', 'SKIP'):
            return 'skip'
        print("  Invalid choice. Please try again.")


def load_csv(conn, csv_path: str, table_name: str, if_exists: str = 'prompt', batch_size: int = 10000):
    print(f"\n\u25b6 Processing: {os.path.basename(csv_path)} \u2192 {table_name}")

    try:
        df = pd.read_csv(csv_path, encoding='utf-8-sig', low_memory=False)
        if df.empty:
            print("  CSV is empty \u2014 skipping.")
            return

        df = optimize_dataframe_types(df)
        print(f"  Rows: {len(df):,} | Columns: {len(df.columns)}")

        exists = table_exists(conn, table_name)

        if exists:
            action = handle_existing_table(conn, table_name, if_exists)
            if action == 'skip':
                print("  Skipping file.")
                return
            elif action == 'replace':
                with conn.cursor() as cur:
                    cur.execute(f'TRUNCATE TABLE "{table_name}"')
                print("  Table truncated.")
            elif action == 'recreate':
                with conn.cursor() as cur:
                    cur.execute(f'DROP TABLE "{table_name}"')
                create_table(conn, table_name, df)
        else:
            create_table(conn, table_name, df)

        # Prepare insert
        clean_cols = [sanitize_identifier(c) for c in df.columns]
        cols_sql = ', '.join([f'"{c}"' for c in clean_cols])
        binds_sql = ', '.join([f':{c}' for c in clean_cols])
        insert_sql = f'INSERT INTO "{table_name}" ({cols_sql}) VALUES ({binds_sql})'

        # Convert NaN \u2192 None for Oracle
        df_clean = df.where(pd.notnull(df), None)
        data = df_clean.to_dict(orient='records')

        total = len(data)
        inserted = 0

        with conn.cursor() as cur:
            for i in range(0, total, batch_size):
                batch = data[i:i + batch_size]
                cur.executemany(insert_sql, batch)
                inserted += len(batch)
                print(f"  Inserted {inserted:,}/{total:,} rows...", end='\r')
            conn.commit()

        print(f"\n  \u2713 Successfully loaded {inserted:,} rows into {table_name}")

    except Exception as e:
        print(f"\n  \u2717 ERROR: {e}")
        try:
            conn.rollback()
        except Exception:
            pass


def parse_file_selection(user_input: str, file_list: list) -> list:
    """Parse '1,3,5', '1-5', or 'all' into list of filenames."""
    user_input = user_input.strip().lower()
    if user_input == 'all':
        return file_list[:]

    selected = []
    for part in re.split(r'[\,\s]+', user_input):
        if not part:
            continue
        if '-' in part:
            try:
                start, end = map(int, part.split('-', 1))
                for idx in range(max(1, start), min(len(file_list), end) + 1):
                    selected.append(file_list[idx - 1])
            except ValueError:
                continue
        elif part.isdigit():
            idx = int(part)
            if 1 <= idx <= len(file_list):
                selected.append(file_list[idx - 1])

    # Deduplicate while preserving order
    seen = set()
    return [f for f in selected if not (f in seen or seen.add(f))]


def main():
    parser = argparse.ArgumentParser(description="Load CSVs into Oracle tables named after the files.")
    parser.add_argument('--dir', '-d', default='.', help='Directory containing CSV files')
    parser.add_argument('--user', '-u', help='Oracle username')
    parser.add_argument('--password', '-p', help='Oracle password (insecure on command line)')
    parser.add_argument('--dsn', help='Easy Connect string, e.g. host:port/service_name')
    parser.add_argument('--if-exists', choices=['prompt', 'append', 'replace', 'recreate', 'skip'],
                        default='prompt', help='Action when table exists')
    parser.add_argument('--batch-size', type=int, default=10000, help='Rows per batch insert')
    parser.add_argument('--create-only', action='store_true', help='Only create tables (no data load)')

    args = parser.parse_args()

    # === Directory & file selection ===
    directory = os.path.abspath(args.dir)
    if not os.path.isdir(directory):
        print(f"Error: Directory not found: {directory}")
        return

    csv_files = sorted([f for f in os.listdir(directory) if f.lower().endswith('.csv')])
    if not csv_files:
        print("No CSV files found in the directory.")
        return

    print(f"\nFound {len(csv_files)} CSV file(s) in: {directory}")
    for i, f in enumerate(csv_files, 1):
        print(f"  {i:2d}. {f}")

    selection = input("\nSelect files (e.g. 1,3,5 or 1-4 or 'all'): ").strip()
    selected_files = parse_file_selection(selection, csv_files)

    if not selected_files:
        print("No files selected. Exiting.")
        return

    # === Database connection ===
    user = args.user or input("Oracle username: ").strip()
    password = args.password or os.getenv('ORACLE_PASSWORD') or getpass.getpass("Oracle password: ")
    dsn = args.dsn or input("Oracle Easy Connect string (host:port/service_name): ").strip()

    print(f"\nConnecting to Oracle as {user}@{dsn} ...")
    try:
        conn = oracledb.connect(user=user, password=password, dsn=dsn)
        print("Connected successfully.\n")
    except oracledb.Error as e:
        print(f"Connection failed: {e}")
        return

    # === Process files ===
    start_time = datetime.now()
    for filename in selected_files:
        csv_path = os.path.join(directory, filename)
        table_name = sanitize_identifier(os.path.splitext(filename)[0])

        if args.create_only:
            # Read only header + few rows for type inference
            try:
                df_sample = pd.read_csv(csv_path, nrows=5, encoding='utf-8-sig')
                df_sample = optimize_dataframe_types(df_sample)
                if not table_exists(conn, table_name):
                    create_table(conn, table_name, df_sample)
                else:
                    print(f"Table {table_name} already exists \u2014 skipping (create-only mode).")
            except Exception as e:
                print(f"Error creating table for {filename}: {e}")
        else:
            load_csv(conn, csv_path, table_name, args.if_exists, args.batch_size)

    conn.close()
    print(f"\nDone in {(datetime.now() - start_time).total_seconds():.1f} seconds.")


if __name__ == "__main__":
    main()
