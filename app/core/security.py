import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from app.core.config import settings

_password_hash = PasswordHash.recommended()  # Argon2


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return _password_hash.verify(password, hashed)


# Usado quando o e-mail não existe ou a conta está bloqueada, para o tempo de
# resposta ser parecido e não revelar quais e-mails estão cadastrados.
DUMMY_HASH = hash_password("dummy-password-for-timing")


def create_access_token(subject: str, token_version: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "tv": token_version,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "jti": uuid.uuid4().hex,
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Levanta jwt.InvalidTokenError se inválido, expirado ou de outro emissor/audiência."""
    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
        audience=settings.JWT_AUDIENCE,
        issuer=settings.JWT_ISSUER,
        options={"require": ["exp", "iat", "sub", "iss", "aud", "tv"]},
    )


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)  # 384 bits de entropia


def hash_refresh_token(token: str) -> str:
    # SHA-256 basta: o token já é aleatório e longo (não precisa de Argon2).
    return hashlib.sha256(token.encode()).hexdigest()
