"""Oracle connection string parsing and database client."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import oracledb


@dataclass(frozen=True)
class ConnectionParams:
    user: str
    password: str
    host: str
    port: int
    service_name: str

    @property
    def dsn(self) -> str:
        return f"{self.host}:{self.port}/{self.service_name}"


def parse_connection_string(conn_str: str) -> ConnectionParams:
    """
    Parse: username/password@host:port/service_name

    Passwords may contain special characters if URL-encoded is not required;
    the split is on the first '@' after user/password.
    """
    pattern = re.compile(
        r"^(?P<user>[^/@:]+)/(?P<password>[^@]+)@"
        r"(?P<host>[^:/]+):(?P<port>\d+)/(?P<service>.+)$"
    )
    match = pattern.match(conn_str.strip())
    if not match:
        raise ValueError(
            "Invalid connection string. Expected: username/password@host:port/service_name"
        )

    return ConnectionParams(
        user=match.group("user"),
        password=match.group("password"),
        host=match.group("host"),
        port=int(match.group("port")),
        service_name=match.group("service"),
    )


def connect(params: ConnectionParams) -> oracledb.Connection:
    """Open a connection to Oracle 19c."""
    return oracledb.connect(
        user=params.user,
        password=params.password,
        dsn=params.dsn,
    )


def table_exists(connection: oracledb.Connection, table_name: str) -> bool:
    owner, name = _split_qualified_name(table_name, connection)
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM ALL_TABLES
            WHERE OWNER = :owner AND TABLE_NAME = :table_name
            """,
            owner=owner,
            table_name=name,
        )
        return cursor.fetchone()[0] > 0


def get_table_columns(
    connection: oracledb.Connection, table_name: str
) -> list[tuple[str, str, int | None]]:
    """Return (column_name, data_type, data_length) for a table."""
    owner, name = _split_qualified_name(table_name, connection)
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COLUMN_NAME, DATA_TYPE, DATA_LENGTH
            FROM ALL_TAB_COLUMNS
            WHERE OWNER = :owner AND TABLE_NAME = :table_name
            ORDER BY COLUMN_ID
            """,
            owner=owner,
            table_name=name,
        )
        return [(row[0], row[1], row[2]) for row in cursor.fetchall()]


def execute_ddl(connection: oracledb.Connection, ddl: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(ddl)
    connection.commit()


def insert_rows(
    connection: oracledb.Connection,
    table_name: str,
    columns: list[str],
    rows: list[tuple[Any, ...]],
    batch_size: int = 1000,
) -> int:
    """Insert rows using executemany with batching."""
    if not rows:
        return 0

    col_list = ", ".join(columns)
    placeholders = ", ".join(f":{i + 1}" for i in range(len(columns)))
    sql = f"INSERT INTO {table_name} ({col_list}) VALUES ({placeholders})"

    inserted = 0
    with connection.cursor() as cursor:
        for start in range(0, len(rows), batch_size):
            batch = rows[start : start + batch_size]
            cursor.executemany(sql, batch)
            inserted += len(batch)
    connection.commit()
    return inserted


def _split_qualified_name(
    table_name: str, connection: oracledb.Connection
) -> tuple[str, str]:
    if "." in table_name:
        owner, name = table_name.split(".", 1)
        return owner.upper(), name.upper()

    with connection.cursor() as cursor:
        cursor.execute("SELECT USER FROM DUAL")
        current_user = cursor.fetchone()[0]
    return current_user.upper(), table_name.upper()
