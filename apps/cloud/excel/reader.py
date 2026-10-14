from io import BytesIO

from python_calamine import CalamineError, CalamineWorkbook, WorksheetNotFound


class InvalidWorkbook(Exception):
    """Indica que el contenido no es un libro XLSX válido."""


class SheetNotFound(Exception):
    """Indica que el libro no contiene la hoja solicitada."""


def _open(content):
    """Abre un XLSX de sólo lectura y normaliza errores de formato.

    @version 1.0
    @author Agustin
    """
    try:
        return CalamineWorkbook.from_filelike(BytesIO(content))
    except CalamineError as error:
        raise InvalidWorkbook from error


def sheets(content):
    """Devuelve los nombres de las hojas del libro XLSX.

    @version 1.0
    @author Agustin
    """
    try:
        with _open(content) as workbook:
            return workbook.sheet_names
    except CalamineError as error:
        raise InvalidWorkbook from error


def read(content, name):
    """Devuelve las filas y valores de una hoja XLSX.

    @version 1.0
    @author Agustin
    """
    try:
        with _open(content) as workbook:
            worksheet = workbook.get_sheet_by_name(name)
            rows = [
                [None if value == "" else value for value in row]
                for row in worksheet.to_python(skip_empty_area=False)
            ]
            return rows
    except WorksheetNotFound as error:
        raise SheetNotFound(name) from error
    except CalamineError as error:
        raise InvalidWorkbook from error
