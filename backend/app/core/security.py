from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from backend.app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(
    user_id: int, store_id: int, expires_delta: Optional[timedelta] = None
) -> str:
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {"user_id": user_id, "store_id": store_id, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


TN_OAUTH_PURPOSE = "tn_oauth"
TN_OAUTH_STATE_TTL_MINUTES = 15


def create_tn_oauth_state(store_id: int) -> str:
    """JWT corto para `state` OAuth TN (MS-ONB01): vincula callback al store del panel."""
    expire = datetime.utcnow() + timedelta(minutes=TN_OAUTH_STATE_TTL_MINUTES)
    payload = {"store_id": store_id, "purpose": TN_OAUTH_PURPOSE, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_tn_oauth_state(token: str) -> Optional[dict]:
    try:
        data = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
    if data.get("purpose") != TN_OAUTH_PURPOSE:
        return None
    if "store_id" not in data:
        return None
    return data
