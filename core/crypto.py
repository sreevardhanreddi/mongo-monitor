from cryptography.fernet import Fernet, InvalidToken

from core.config import get_settings


def _fernet() -> Fernet | None:
    key = get_settings().encryption_key
    return Fernet(key.encode()) if key else None


def encrypt_uri(plain: str) -> str:
    f = _fernet()
    if f is None:
        return plain
    return f.encrypt(plain.encode()).decode()


def decrypt_uri(value: str) -> str:
    f = _fernet()
    if f is None:
        return value
    try:
        return f.decrypt(value.encode()).decode()
    except InvalidToken:
        # Legacy plaintext record written before encryption was enabled —
        # return as-is so existing monitors keep working until next save.
        return value
