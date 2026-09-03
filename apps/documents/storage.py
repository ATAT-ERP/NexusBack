from abc import ABC, abstractmethod
from typing import BinaryIO


class FileStorage(ABC):
    """Contrato para el proveedor que persiste los archivos del módulo."""

    @abstractmethod
    def save(self, storage_key: str, content: BinaryIO, mime_type: str) -> None:
        """Guarda el contenido en la clave interna indicada."""

    @abstractmethod
    def open(self, storage_key: str) -> BinaryIO:
        """Abre el contenido asociado a una clave interna."""

    @abstractmethod
    def delete(self, storage_key: str) -> None:
        """Elimina el contenido asociado a una clave interna."""

