"""Orchestrates the CSV-to-Oracle loading workflow."""

from __future__ import annotations

from pathlib import Path

from src import prompts
from src.connection import (
    connect,
    execute_ddl,
    get_table_columns,
    insert_rows,
    parse_connection_string,
    table_exists,
)
from src.schema import (
    build_create_table_ddl,
    dataframe_to_rows,
    infer_columns,
    map_csv_to_table_columns,
    read_csv_for_inference,
    read_csv_for_load,
    validate_csv_columns_match,
)


def run() -> None:
    print("CSV to Oracle 19c Loader")
    print("=" * 40)

    directory = prompts.prompt_directory()
    csv_files = prompts.select_csv_files(directory)
    conn_str = prompts.prompt_connection_string()
    create_new = prompts.prompt_create_table()

    try:
        params = parse_connection_string(conn_str)
    except ValueError as exc:
        print(f"\nError: {exc}")
        return

    print("\nConnecting to Oracle...")
    try:
        connection = connect(params)
    except Exception as exc:
        print(f"\nConnection failed: {exc}")
        return

    print("Connected successfully.")

    try:
        first_csv = csv_files[0]
        df = read_csv_for_inference(first_csv)
        if df.empty:
            print(f"\nError: {first_csv.name} has no data rows.")
            return

        columns = infer_columns(df)

        if create_new:
            table_name = prompts.prompt_new_table_name()
            if table_exists(connection, table_name):
                print(f"\nError: Table {table_name} already exists.")
                return

            ddl = build_create_table_ddl(table_name, columns)
            if not prompts.confirm_schema(ddl):
                print("\nAborted. Table was not created.")
                return

            print("\nCreating table...")
            execute_ddl(connection, ddl)
            print(f"Table {table_name} created.")
        else:
            table_name = prompts.prompt_table_name()
            if not table_exists(connection, table_name):
                print(f"\nError: Table {table_name} does not exist.")
                return

            db_columns = get_table_columns(connection, table_name)
            db_names, columns, _ = map_csv_to_table_columns(df, db_columns)
            if not db_names:
                print(
                    f"\nError: No CSV columns match table {table_name}. "
                    "Check that headers align with table column names."
                )
                return

            unmapped = len(df.columns) - len(db_names)
            if unmapped:
                print(
                    f"\nNote: {unmapped} CSV column(s) have no match in "
                    f"{table_name} and will be skipped."
                )
            print(f"Mapped {len(db_names)} column(s) for insert.")

        total_inserted = 0
        for csv_path in csv_files:
            file_df = read_csv_for_load(csv_path)

            if create_new:
                if csv_path != first_csv:
                    ok, message = validate_csv_columns_match(columns, csv_path)
                    if not ok:
                        print(f"\nSkipping {csv_path.name}: {message}")
                        continue
                rows = dataframe_to_rows(file_df, columns)
                col_names = [f'"{col.name}"' for col in columns]
            else:
                table_cols = get_table_columns(connection, table_name)
                mapped_names, file_columns, file_indices = map_csv_to_table_columns(
                    file_df, table_cols
                )
                if not mapped_names:
                    print(f"\nSkipping {csv_path.name}: no columns match {table_name}")
                    continue
                rows = dataframe_to_rows(file_df, file_columns, file_indices)
                col_names = [f'"{name}"' for name in mapped_names]
            count = insert_rows(connection, table_name, col_names, rows)
            total_inserted += count
            print(f"  Inserted {count:,} rows from {csv_path.name}")

        print(f"\nDone. Total rows inserted: {total_inserted:,} into {table_name}.")
    finally:
        connection.close()
