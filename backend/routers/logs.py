import os
import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import func
from sqlmodel import Session, desc, select

from database import get_session
from models import LogEntry, LogEntryRead

router = APIRouter(prefix="/api", tags=["logs"])
security = HTTPBasic()

LOGS_USER = os.getenv("LOGS_USER", "")
LOGS_PASS = os.getenv("LOGS_PASS", "")


def verify_logs_credentials(
    credentials: HTTPBasicCredentials = Depends(security),
):
    correct_user = secrets.compare_digest(credentials.username, LOGS_USER)
    correct_pass = secrets.compare_digest(credentials.password, LOGS_PASS)
    if not (correct_user and correct_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


@router.get("/logs", response_model=list[LogEntryRead])
def get_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    event_type: str | None = None,
    user_filter: str | None = Query(None, alias="user"),
    search: str | None = None,
    _: str = Depends(verify_logs_credentials),
    session: Session = Depends(get_session),
):
    statement = select(LogEntry).order_by(desc(LogEntry.timestamp))
    if event_type:
        statement = statement.where(LogEntry.event_type == event_type)
    if user_filter:
        statement = statement.where(LogEntry.user == user_filter)
    if search:
        statement = statement.where(LogEntry.path.contains(search))
    statement = statement.offset(skip).limit(limit)
    return session.exec(statement).all()


@router.get("/logs/count")
def get_logs_count(
    event_type: str | None = None,
    user_filter: str | None = Query(None, alias="user"),
    search: str | None = None,
    _: str = Depends(verify_logs_credentials),
    session: Session = Depends(get_session),
):
    statement = select(func.count()).select_from(LogEntry)
    if event_type:
        statement = statement.where(LogEntry.event_type == event_type)
    if user_filter:
        statement = statement.where(LogEntry.user == user_filter)
    if search:
        statement = statement.where(LogEntry.path.contains(search))
    count = session.exec(statement).one()
    return {"count": count}
