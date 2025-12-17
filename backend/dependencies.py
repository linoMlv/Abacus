from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session, select
from typing import Optional
from jose import jwt, JWTError

from database import get_session
from models import Association
from security import SECRET_KEY, ALGORITHM

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/login", auto_error=False)

async def get_token(request: Request, token: Optional[str] = Depends(oauth2_scheme)):
    if token:
        return token
    token = request.cookies.get("access_token")
    if token:
        if token.startswith("Bearer "):
            return token.split(" ")[1]
        return token
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )

async def get_current_association(token: str = Depends(get_token), session: Session = Depends(get_session)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        name: str = payload.get("sub")
        if name is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    statement = select(Association).where(Association.name == name)
    association = session.exec(statement).first()
    if association is None:
        raise credentials_exception
    return association
