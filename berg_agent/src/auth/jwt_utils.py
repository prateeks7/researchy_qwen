import os
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

SECRET_KEY = os.getenv("JWT_SECRET", "dev-secret-please-change-in-production")
ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 7

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def create_token(user_id: str, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": user_id, "email": email, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    return decode_token(token)
