"""Carga inicial de roles, permisos, el usuario administrador y una API Key de servicio.

Es idempotente: se puede ejecutar en cada despliegue sin duplicar datos. Se invoca con
`python -m scripts.seed` teniendo instalado el paquete de la API.
"""
import os

from app.domain.permissions import PERMISSIONS, ROLES
from app.infrastructure.db import SessionFactory
from app.infrastructure.security.hashing import hash_password, hash_token
from payment_db_models.models import ApiKey, Permission, Role, User
from sqlalchemy import select


def run() -> None:
    session = SessionFactory()
    try:
        perms = _sync_permissions(session)
        _sync_roles(session, perms)
        _sync_admin(session)
        _sync_service_key(session)
        session.commit()
        print("Seed complete.")
    finally:
        session.close()


def _sync_permissions(session) -> dict[str, Permission]:
    existing = {p.code: p for p in session.scalars(select(Permission))}
    for code in PERMISSIONS:
        if code not in existing:
            perm = Permission(code=code)
            session.add(perm)
            existing[code] = perm
    session.flush()
    return existing


def _sync_roles(session, perms: dict[str, Permission]) -> None:
    for name, codes in ROLES.items():
        role = session.scalar(select(Role).where(Role.name == name))
        if role is None:
            role = Role(name=name)
            session.add(role)
        role.permissions = [perms[c] for c in codes]
    session.flush()


def _sync_admin(session) -> None:
    email = os.environ.get("ADMIN_EMAIL", "admin@payments.com")
    password = os.environ.get("ADMIN_PASSWORD", "admin12345")
    admin = session.scalar(select(User).where(User.email == email))
    if admin is None:
        admin = User(email=email, hashed_password=hash_password(password))
        session.add(admin)
    admin.roles = [session.scalar(select(Role).where(Role.name == "ADMIN"))]


def _sync_service_key(session) -> None:
    raw_key = os.environ.get("SERVICE_API_KEY")
    if not raw_key:
        return
    hashed = hash_token(raw_key)
    if session.scalar(select(ApiKey).where(ApiKey.hashed_key == hashed)) is None:
        session.add(ApiKey(name="default-service", hashed_key=hashed))


if __name__ == "__main__":
    run()
