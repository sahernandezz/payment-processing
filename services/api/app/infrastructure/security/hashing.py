import hashlib

import bcrypt

# bcrypt only reads the first 72 bytes of the input.
_MAX_BCRYPT_BYTES = 72


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode()[:_MAX_BCRYPT_BYTES], bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode()[:_MAX_BCRYPT_BYTES], hashed.encode())


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
