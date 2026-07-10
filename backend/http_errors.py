"""Small factories for the HTTP errors raised across the routers.

``HTTPException(status_code=400, detail=…)`` was rewritten verbatim in every
service module; centralising it keeps the error contract in one place (and makes
a future change — logging, a uniform body — a one-liner).
"""

from fastapi import HTTPException, status


def bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
