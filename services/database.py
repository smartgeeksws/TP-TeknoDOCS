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


def initialize_schema() -> None:
    """Incorpora de forma idempotente empresas y datos nuevos de proyecto."""

    try:
        with database_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS empresas (
                    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    nit VARCHAR(30) NOT NULL,
                    razon_social VARCHAR(220) NOT NULL,
                    activo BOOLEAN NOT NULL DEFAULT TRUE,
                    creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    actualizado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                        ON UPDATE CURRENT_TIMESTAMP,
                    CONSTRAINT uk_empresa_nit UNIQUE (nit)
                ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
                """
            )
            cursor.execute(
                """
                SELECT IS_NULLABLE
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'empresas'
                  AND COLUMN_NAME = 'nombre'
                """
            )
            legacy_name = cursor.fetchone()
            if legacy_name is not None and legacy_name[0] == "NO":
                cursor.execute(
                    "ALTER TABLE empresas MODIFY nombre VARCHAR(180) NULL"
                )
            cursor.execute(
                """
                SELECT COLUMN_NAME, COLUMN_TYPE
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'proyectos'
                  AND COLUMN_NAME IN (
                      'empresa_propietaria_id', 'empresa_id', 'linea_tecnologica',
                      'trl_inicial', 'trl_objetivo'
                  )
                """
            )
            columns = dict(cursor.fetchall())
            if "empresa_propietaria_id" not in columns:
                cursor.execute(
                    """ALTER TABLE proyectos
                    ADD empresa_propietaria_id BIGINT UNSIGNED NULL"""
                )
            elif columns["empresa_propietaria_id"].lower() != "bigint unsigned":
                cursor.execute(
                    """ALTER TABLE proyectos
                    MODIFY empresa_propietaria_id BIGINT UNSIGNED NULL"""
                )
            if "linea_tecnologica" not in columns:
                cursor.execute(
                    "ALTER TABLE proyectos ADD linea_tecnologica VARCHAR(120) NULL"
                )
            if "trl_inicial" not in columns:
                cursor.execute(
                    """ALTER TABLE proyectos ADD trl_inicial
                    ENUM('TRL 1','TRL 2','TRL 3','TRL 4','TRL 5',
                         'TRL 6','TRL 7','TRL 8','TRL 9') NULL"""
                )
            if "trl_objetivo" not in columns:
                cursor.execute(
                    """ALTER TABLE proyectos ADD trl_objetivo
                    ENUM('TRL 1','TRL 2','TRL 3','TRL 4','TRL 5',
                         'TRL 6','TRL 7','TRL 8','TRL 9') NULL"""
                )
            if "empresa_id" in columns:
                cursor.execute(
                    """UPDATE proyectos
                    SET empresa_propietaria_id = empresa_id
                    WHERE empresa_propietaria_id IS NULL
                      AND empresa_id IS NOT NULL"""
                )
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM information_schema.TABLE_CONSTRAINTS
                WHERE CONSTRAINT_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'proyectos'
                  AND CONSTRAINT_NAME = 'fk_proyectos_empresa_propietaria'
                """
            )
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    """
                    ALTER TABLE proyectos
                    ADD CONSTRAINT fk_proyectos_empresa_propietaria
                    FOREIGN KEY (empresa_propietaria_id) REFERENCES empresas(id)
                    """
                )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS documentos_proyecto (
                    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    proyecto_id BIGINT UNSIGNED NOT NULL,
                    clave_documento VARCHAR(80) NOT NULL,
                    datos_formulario LONGTEXT NOT NULL,
                    contenido_generado LONGTEXT NULL,
                    fuentes_json LONGTEXT NULL,
                    generado_en DATETIME NULL,
                    cantidad_generaciones INT UNSIGNED NOT NULL DEFAULT 0,
                    creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    actualizado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                        ON UPDATE CURRENT_TIMESTAMP,
                    CONSTRAINT uk_documento_proyecto UNIQUE
                        (proyecto_id, clave_documento),
                    CONSTRAINT fk_documento_proyecto
                        FOREIGN KEY (proyecto_id) REFERENCES proyectos(id)
                ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
                """
            )
            connection.commit()
            cursor.close()
    except mysql.connector.Error as error:
        raise DatabaseError(
            f"No fue posible actualizar la estructura de la base de datos: {error}"
        ) from error
