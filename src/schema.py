"""CSV schema inference and Oracle DDL generation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class ColumnDef:
    name: str
    oracle_type: str

    def ddl_fragment(self) -> str:
        return f'"{self.name}" {self.oracle_type}'


def sanitize_column_name(raw: str) -> str:
    """Convert a CSV header to a valid Oracle identifier."""
    name = raw.strip().upper()
    name = re.sub(r"[^A-Z0-9_]", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    if not name:
        name = "COL"
    if name[0].isdigit():
        name = f"C_{name}"
    return name[:128]


def read_csv_for_inference(path: Path) -> pd.DataFrame:
    """Read a CSV file and let pandas infer types for schema detection."""
    return pd.read_csv(path, keep_default_na=True, na_values=["", "NA", "N/A", "null"])


def read_csv_for_load(path: Path) -> pd.DataFrame:
    """Read a CSV file for row insertion."""
    return pd.read_csv(path, keep_default_na=True, na_values=["", "NA", "N/A", "null"])


def infer_columns(df: pd.DataFrame) -> list[ColumnDef]:
    """Infer Oracle column types from a DataFrame."""
    columns: list[ColumnDef] = []
    used_names: dict[str, int] = {}

    for raw_name in df.columns:
        base_name = sanitize_column_name(str(raw_name))
        if base_name in used_names:
            used_names[base_name] += 1
            col_name = f"{base_name}_{used_names[base_name]}"
        else:
            used_names[base_name] = 0
            col_name = base_name

        series = df[raw_name].replace("", pd.NA).dropna()
        oracle_type = _infer_oracle_type(series)
        columns.append(ColumnDef(name=col_name, oracle_type=oracle_type))

    return columns


def build_create_table_ddl(table_name: str, columns: list[ColumnDef]) -> str:
    col_defs = ",\n    ".join(col.ddl_fragment() for col in columns)
    return f'CREATE TABLE {table_name} (\n    {col_defs}\n)'


def map_csv_to_table_columns(
    df: pd.DataFrame,
    table_columns: list[tuple[str, str, int | None]],
) -> tuple[list[str], list[ColumnDef], list[int]]:
    """
    Map CSV headers to existing table columns by sanitized name.

    Returns (db_column_names, column_defs_for_coercion, csv_column_indices).
    """
    table_by_name = {name: (name, dtype, length) for name, dtype, length in table_columns}
    db_names: list[str] = []
    col_defs: list[ColumnDef] = []
    csv_indices: list[int] = []

    for idx, raw_header in enumerate(df.columns):
        sanitized = sanitize_column_name(str(raw_header))
        if sanitized not in table_by_name:
            continue
        db_name, data_type, _ = table_by_name[sanitized]
        oracle_type = _oracle_type_from_db(data_type)
        db_names.append(db_name)
        col_defs.append(ColumnDef(name=db_name, oracle_type=oracle_type))
        csv_indices.append(idx)

    return db_names, col_defs, csv_indices


def dataframe_to_rows(
    df: pd.DataFrame,
    columns: list[ColumnDef],
    csv_indices: list[int] | None = None,
) -> list[tuple]:
    """Convert DataFrame rows to tuples aligned with column definitions."""
    indices = csv_indices if csv_indices is not None else list(range(len(columns)))
    rows: list[tuple] = []
    for _, record in df.iterrows():
        row_values = []
        for col, csv_idx in zip(columns, indices):
            raw = record.iloc[csv_idx]
            row_values.append(_coerce_value(raw, col.oracle_type))
        rows.append(tuple(row_values))
    return rows


def validate_csv_columns_match(
    reference: list[ColumnDef], other_path: Path
) -> tuple[bool, str]:
    """Check that another CSV has the same column count and compatible headers."""
    other_df = read_csv_for_inference(other_path)
    if len(other_df.columns) != len(reference):
        return (
            False,
            f"{other_path.name}: expected {len(reference)} columns, "
            f"found {len(other_df.columns)}",
        )

    ref_headers = [sanitize_column_name(str(h)) for h in other_df.columns]
    expected = [col.name for col in reference]
    if ref_headers != expected:
        return (
            False,
            f"{other_path.name}: column headers do not match the first file",
        )
    return True, ""


def _infer_oracle_type(series: pd.Series) -> str:
    if series.empty:
        return "VARCHAR2(4000)"

    if _all_integers(series):
        return "NUMBER(18)"

    if _all_numeric(series):
        return "NUMBER(18, 6)"

    if _all_booleans(series):
        return "NUMBER(1)"

    if _all_dates(series):
        return "TIMESTAMP"

    max_len = int(series.astype(str).str.len().max())
    if max_len <= 4000:
        size = max(50, min(4000, _next_varchar_size(max_len)))
        return f"VARCHAR2({size})"
    return "CLOB"


def _all_integers(series: pd.Series) -> bool:
    try:
        converted = pd.to_numeric(series, errors="coerce")
        if converted.isna().any():
            return False
        return (converted % 1 == 0).all()
    except (TypeError, ValueError):
        return False


def _all_numeric(series: pd.Series) -> bool:
    converted = pd.to_numeric(series, errors="coerce")
    return not converted.isna().any()


def _all_booleans(series: pd.Series) -> bool:
    normalized = series.astype(str).str.strip().str.lower()
    allowed = {"true", "false", "1", "0", "y", "n", "yes", "no"}
    return normalized.isin(allowed).all()


def _all_dates(series: pd.Series) -> bool:
    parsed = pd.to_datetime(series, errors="coerce")
    return not parsed.isna().any()


def _oracle_type_from_db(data_type: str) -> str:
    return data_type.upper()


def _next_varchar_size(length: int) -> int:
    for size in (50, 100, 255, 500, 1000, 2000, 4000):
        if length <= size:
            return size
    return 4000


def _coerce_value(raw: object, oracle_type: str):
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    text = str(raw).strip()
    if text == "":
        return None

    upper_type = oracle_type.upper()
    if upper_type.startswith("NUMBER"):
        if _all_booleans(pd.Series([text])):
            return 1 if text.lower() in {"true", "1", "y", "yes"} else 0
        numeric = pd.to_numeric(text, errors="coerce")
        return None if pd.isna(numeric) else float(numeric)

    if upper_type.startswith("TIMESTAMP") or upper_type == "DATE":
        parsed = pd.to_datetime(text, errors="coerce")
        return None if pd.isna(parsed) else parsed.to_pydatetime()

    return text
