"""Almacenamiento privado de firmas en un servidor FTPS."""

from __future__ import annotations

import ssl
from contextlib import contextmanager
from ftplib import FTP, FTP_TLS, Error as FTPError, error_perm
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterator
from uuid import UUID, uuid4

from docx.image.exceptions import (
    InvalidImageStreamError,
    UnexpectedEndOfFileError,
    UnrecognizedImageError,
)
from docx.image.image import Image
import streamlit as st

from config.settings import ROOT_DIR, SIGNATURES_DIR


class SignatureStorageError(ValueError):
    """Error controlado de configuración o comunicación con el almacén privado."""


class SignatureStorage:
    """Guarda y recupera firmas privadas mediante FTPS explícito."""

    REFERENCE_PREFIX = "signature:"
    MAX_FILE_SIZE = 2 * 1024 * 1024
    TIMEOUT_SECONDS = 20
    BLOCK_SIZE = 64 * 1024
    ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg"}

    def __init__(
        self,
        settings: dict[str, Any] | None = None,
        ftp_factory: Callable[..., FTP_TLS] = FTP_TLS,
    ) -> None:
        self._provided_settings = dict(settings) if settings is not None else None
        self._ftp_factory = ftp_factory

    def save(self, original_name: str, data: bytes) -> str:
        """Sube una firma de forma atómica y retorna una referencia privada."""

        extension = self._validate_image(original_name, data)
        filename = f"{uuid4()}{extension}"
        temporary_name = f".{filename}.{uuid4().hex}.part"
        settings = self._settings()

        try:
            with self._connection(settings) as ftp:
                self._change_directory(ftp, settings["remote_dir"], create=True)
                try:
                    ftp.storbinary(
                        f"STOR {temporary_name}",
                        BytesIO(data),
                        blocksize=self.BLOCK_SIZE,
                    )
                    ftp.rename(temporary_name, filename)
                except (FTPError, OSError, EOFError):
                    try:
                        ftp.delete(temporary_name)
                    except (FTPError, OSError, EOFError):
                        pass
                    raise
        except SignatureStorageError:
            raise
        except error_perm as error:
            raise SignatureStorageError(
                "El servidor FTPS rechazó la carga de la firma. Verifica los "
                "permisos de la carpeta privada /firmas."
            ) from error
        except (FTPError, OSError, EOFError) as error:
            raise SignatureStorageError(
                "No fue posible guardar la firma en el servidor FTPS privado."
            ) from error

        return f"{self.REFERENCE_PREFIX}{filename}"

    def load(self, reference: str) -> BytesIO:
        """Descarga una firma remota y la retorna en memoria."""

        filename = self._remote_filename(reference)
        settings = self._settings()
        buffer = BytesIO()

        def write_chunk(chunk: bytes) -> None:
            if buffer.tell() + len(chunk) > self.MAX_FILE_SIZE:
                raise SignatureStorageError(
                    "La firma almacenada supera el límite permitido de 2 MB."
                )
            buffer.write(chunk)

        try:
            with self._connection(settings) as ftp:
                self._change_directory(ftp, settings["remote_dir"])
                ftp.retrbinary(
                    f"RETR {filename}",
                    write_chunk,
                    blocksize=self.BLOCK_SIZE,
                )
        except SignatureStorageError:
            raise
        except error_perm as error:
            raise SignatureStorageError(
                "La firma no está disponible en el almacenamiento FTPS privado. "
                "Vuelve a cargarla desde Editar proyecto."
            ) from error
        except (FTPError, OSError, EOFError) as error:
            raise SignatureStorageError(
                "No fue posible recuperar la firma desde el servidor FTPS privado."
            ) from error

        data = buffer.getvalue()
        self._validate_image(filename, data)
        buffer.seek(0)
        return buffer

    def open(self, reference: str) -> Path | BytesIO:
        """Abre una referencia FTPS o una ruta local heredada segura."""

        if self.is_remote_reference(reference):
            return self.load(reference)
        return self._legacy_path(reference)

    def delete(self, reference: str | None) -> None:
        """Elimina una firma remota; nunca elimina rutas locales heredadas."""

        if not reference or not self.is_remote_reference(reference):
            return
        filename = self._remote_filename(reference)
        settings = self._settings()
        try:
            with self._connection(settings) as ftp:
                self._change_directory(ftp, settings["remote_dir"])
                ftp.delete(filename)
        except error_perm as error:
            raise SignatureStorageError(
                "El servidor FTPS rechazó la eliminación de una firma anterior."
            ) from error
        except (FTPError, OSError, EOFError) as error:
            raise SignatureStorageError(
                "No fue posible eliminar una firma anterior del servidor FTPS."
            ) from error

    @classmethod
    def is_remote_reference(cls, reference: str | None) -> bool:
        return bool(reference and reference.startswith(cls.REFERENCE_PREFIX))

    @contextmanager
    def _connection(self, settings: dict[str, Any]) -> Iterator[FTP_TLS]:
        context = ssl.create_default_context()
        ftp: FTP_TLS | None = None
        try:
            ftp = self._ftp_factory(context=context)
            ftp.encoding = "utf-8"
            ftp.connect(
                settings["host"],
                settings["port"],
                timeout=self.TIMEOUT_SECONDS,
            )
            ftp.login(settings["username"], settings["password"])
            ftp.set_pasv(True)
            ftp.prot_p()
        except error_perm as error:
            if ftp is not None:
                try:
                    ftp.close()
                except (FTPError, OSError, EOFError):
                    pass
            raise SignatureStorageError(
                "El servidor FTPS rechazó las credenciales configuradas."
            ) from error
        except (FTPError, OSError, EOFError) as error:
            if ftp is not None:
                try:
                    ftp.close()
                except (FTPError, OSError, EOFError):
                    pass
            raise SignatureStorageError(
                "No fue posible establecer una conexión FTPS segura."
            ) from error

        try:
            yield ftp
        finally:
            try:
                ftp.quit()
            except (FTPError, OSError, EOFError):
                try:
                    ftp.close()
                except (FTPError, OSError, EOFError):
                    pass

    @staticmethod
    def _change_directory(
        ftp: FTP,
        remote_dir: str,
        *,
        create: bool = False,
    ) -> None:
        try:
            ftp.cwd(remote_dir)
        except error_perm:
            if not create:
                raise
            ftp.mkd(remote_dir)
            ftp.cwd(remote_dir)

    def _settings(self) -> dict[str, Any]:
        if self._provided_settings is not None:
            raw = self._provided_settings
        else:
            try:
                raw = dict(st.secrets["storage"])
            except Exception as error:
                raise SignatureStorageError(
                    "Configura la sección [storage] en los Secrets de Streamlit."
                ) from error

        storage_type = str(raw.get("type") or "").strip().lower()
        if storage_type != "ftps":
            raise SignatureStorageError(
                "La configuración [storage] debe usar type = \"ftps\"."
            )
        required = ("host", "port", "username", "password", "remote_dir")
        missing = [key for key in required if not str(raw.get(key) or "").strip()]
        if missing:
            raise SignatureStorageError(
                "Faltan valores en [storage]: " + ", ".join(missing) + "."
            )
        try:
            port = int(raw["port"])
        except (TypeError, ValueError) as error:
            raise SignatureStorageError(
                "El puerto configurado para FTPS no es válido."
            ) from error
        if not 1 <= port <= 65535:
            raise SignatureStorageError(
                "El puerto configurado para FTPS no es válido."
            )

        remote_dir = self._normalize_remote_dir(str(raw["remote_dir"]))
        return {
            "host": str(raw["host"]).strip(),
            "port": port,
            "username": str(raw["username"]).strip(),
            "password": str(raw["password"]),
            "remote_dir": remote_dir,
        }

    @staticmethod
    def _normalize_remote_dir(value: str) -> str:
        path = PurePosixPath(value.strip().replace("\\", "/"))
        parts = [part for part in path.parts if part not in {"/", ""}]
        if not parts or any(part in {".", ".."} for part in parts):
            raise SignatureStorageError(
                "La carpeta remota de firmas no es válida."
            )
        return "/" + "/".join(parts)

    @classmethod
    def _remote_filename(cls, reference: str) -> str:
        if not cls.is_remote_reference(reference):
            raise SignatureStorageError("La referencia de firma remota no es válida.")
        filename = reference[len(cls.REFERENCE_PREFIX):].strip()
        path = PurePosixPath(filename)
        if not filename or path.name != filename or filename in {".", ".."}:
            raise SignatureStorageError("La referencia de firma remota no es válida.")
        if path.suffix.lower() not in cls.ALLOWED_EXTENSIONS:
            raise SignatureStorageError("La referencia de firma remota no es válida.")
        try:
            identifier = UUID(path.stem)
        except (ValueError, AttributeError) as error:
            raise SignatureStorageError(
                "La referencia de firma remota no es válida."
            ) from error
        if str(identifier) != path.stem.lower():
            raise SignatureStorageError("La referencia de firma remota no es válida.")
        return filename

    @classmethod
    def _validate_image(cls, name: str, data: bytes) -> str:
        extension = Path(name).suffix.lower()
        if extension not in cls.ALLOWED_EXTENSIONS:
            raise SignatureStorageError(
                "La firma debe ser una imagen PNG, JPG o JPEG."
            )
        if not data:
            raise SignatureStorageError("La imagen de la firma está vacía.")
        if len(data) > cls.MAX_FILE_SIZE:
            raise SignatureStorageError(
                "La imagen de la firma no puede superar 2 MB."
            )
        is_png = data.startswith(b"\x89PNG\r\n\x1a\n")
        is_jpeg = data.startswith(b"\xff\xd8\xff")
        if extension == ".png" and not is_png:
            raise SignatureStorageError("El archivo cargado no es una imagen PNG válida.")
        if extension in {".jpg", ".jpeg"} and not is_jpeg:
            raise SignatureStorageError("El archivo cargado no es una imagen JPEG válida.")
        try:
            Image.from_file(BytesIO(data))
        except (
            InvalidImageStreamError,
            UnexpectedEndOfFileError,
            UnrecognizedImageError,
        ) as error:
            raise SignatureStorageError(
                "La imagen de la firma está incompleta o dañada."
            ) from error
        return ".jpg" if extension == ".jpeg" else extension

    @staticmethod
    def _legacy_path(reference: str) -> Path:
        if not reference:
            raise SignatureStorageError("No hay una firma registrada.")
        normalized = reference.replace("\\", "/")
        path = Path(normalized)
        if not path.is_absolute():
            path = ROOT_DIR / path
        try:
            resolved = path.resolve(strict=False)
            resolved.relative_to(SIGNATURES_DIR.resolve(strict=False))
        except (OSError, ValueError) as error:
            raise SignatureStorageError(
                "La referencia local heredada de la firma no es válida."
            ) from error
        if not resolved.is_file():
            raise SignatureStorageError(
                "La firma local anterior ya no está disponible. Vuelve a cargarla "
                "desde Editar proyecto para guardarla en el servidor privado."
            )
        return resolved
