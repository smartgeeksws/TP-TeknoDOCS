"""Conexión centralizada a MySQL mediante secretos de Streamlit."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import mysql.connector
import streamlit as st
from mysql.connector.connection import MySQLConnection


class DatabaseError(RuntimeError):
    """Error de configuración o comunicación con la base de datos."""


def _connection_settings() -> dict:
    try:
        mysql_secrets = st.secrets["mysql"]
    except Exception as error:
        raise DatabaseError(
            "No se encontró la configuración MySQL. "
            "Crea .streamlit/secrets.toml a partir de secrets.toml.example."
        ) from error

    required = ("host", "port", "database", "user", "password")
    missing = [key for key in required if not mysql_secrets.get(key)]
    if missing:
        raise DatabaseError(
            f"Faltan valores MySQL en secrets.toml: {', '.join(missing)}."
        )

    return {
        "host": mysql_secrets["host"],
        "port": int(mysql_secrets["port"]),
        "database": mysql_secrets["database"],
        "user": mysql_secrets["user"],
        "password": mysql_secrets["password"],
        "charset": "utf8mb4",
        "collation": "utf8mb4_unicode_ci",
        "connection_timeout": 10,
        "autocommit": False,
    }


@contextmanager
def database_connection() -> Iterator[MySQLConnection]:
    """Entrega una conexión y garantiza rollback y cierre ante errores."""

    try:
        connection = mysql.connector.connect(**_connection_settings())
    except DatabaseError:
        raise
    except mysql.connector.Error as error:
        raise DatabaseError(f"No fue posible conectar con MySQL: {error}") from error

    try:
        yield connection
    except Exception:
        connection.rollback()
        raise
    finally:
        if connection.is_connected():
            connection.close()
