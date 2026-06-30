from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login", auto_error=False)


async def get_token(request: Request, token: str | None = Depends(oauth2_scheme)):
    """Resolve the bearer token from the Authorization header or the access cookie."""
    if token:
        return token
    token = request.cookies.get("access_token")
    if token:
        if token.startswith("Bearer "):
            return token.split(" ")[1]
        return token
    return None
