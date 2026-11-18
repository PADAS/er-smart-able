"""An error the API returns: its English text stays in `detail`, and a stable `code` (with the values
the text names) lets the browser show it in the reader's language."""
from fastapi import HTTPException


class ApiError(HTTPException):
    def __init__(self, status_code: int, code: str, detail: str, **values):
        super().__init__(status_code=status_code, detail=detail)
        self.code = code
        self.values = values
