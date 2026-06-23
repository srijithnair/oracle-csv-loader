"""Interactive CLI prompts for the CSV-to-Oracle loader."""

from __future__ import annotations

import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog


def prompt_directory() -> Path:
    """Ask for a directory path and validate it exists."""
    while True:
        raw = input("\nEnter directory path containing CSV files: ").strip()
        if not raw:
            print("Directory path is required.")
            continue

        path = Path(raw).expanduser().resolve()
        if not path.exists():
            print(f"Path does not exist: {path}")
            continue
        if not path.is_dir():
            print(f"Path is not a directory: {path}")
            continue
        return path


def select_csv_files(directory: Path) -> list[Path]:
    """Open a file picker to select one or more CSV files."""
    print(f"\nOpening file picker in: {directory}")
    print("Select one or more CSV files (Cmd/Ctrl+click for multiple).")

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    selected = filedialog.askopenfilenames(
        title="Select CSV files",
        initialdir=str(directory),
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
    )
    root.destroy()

    if not selected:
        print("No files selected.")
        retry = input("Try again? [y/N]: ").strip().lower()
        if retry in {"y", "yes"}:
            return select_csv_files(directory)
        sys.exit(0)

    paths = [Path(p).resolve() for p in selected]
    print("\nSelected files:")
    for path in paths:
        print(f"  - {path.name}")
    return paths


def prompt_connection_string() -> str:
    """Ask for an Oracle connection string."""
    print(
        "\nEnter Oracle connection string.\n"
        "Format: username/password@host:port/service_name\n"
        "Example: scott/tiger@localhost:1521/ORCLPDB1"
    )
    while True:
        conn_str = input("Connection string: ").strip()
        if conn_str:
            return conn_str
        print("Connection string is required.")


def prompt_create_table() -> bool:
    """Ask whether a new table should be created."""
    while True:
        answer = input("\nCreate a new table? [y/N]: ").strip().lower()
        if answer in {"", "n", "no"}:
            return False
        if answer in {"y", "yes"}:
            return True
        print("Please answer y or n.")


def prompt_table_name() -> str:
    """Ask for an existing Oracle table name."""
    while True:
        name = input("\nEnter target table name: ").strip().upper()
        if name:
            return name
        print("Table name is required.")


def prompt_new_table_name() -> str:
    """Ask for the name of the table to create."""
    while True:
        name = input("\nEnter new table name: ").strip().upper()
        if name:
            return name
        print("Table name is required.")


def confirm_schema(ddl: str) -> bool:
    """Show proposed DDL and wait for user confirmation."""
    print("\n" + "=" * 60)
    print("Proposed table schema:")
    print("=" * 60)
    print(ddl)
    print("=" * 60)

    while True:
        answer = input("\nExecute this CREATE TABLE statement? [y/N]: ").strip().lower()
        if answer in {"", "n", "no"}:
            return False
        if answer in {"y", "yes"}:
            return True
        print("Please answer y or n.")


def confirm_proceed(message: str) -> bool:
    """Generic yes/no confirmation."""
    while True:
        answer = input(f"\n{message} [y/N]: ").strip().lower()
        if answer in {"", "n", "no"}:
            return False
        if answer in {"y", "yes"}:
            return True
        print("Please answer y or n.")
