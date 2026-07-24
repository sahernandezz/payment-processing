PERMISSIONS: list[str] = [
    "merchants:create",
    "merchants:read",
    "payments:create",
    "payments:read",
    "payments:transition",
    "roles:manage",
]

ROLES: dict[str, list[str]] = {
    "ADMIN": list(PERMISSIONS),
    "OPERATOR": ["merchants:read", "payments:create", "payments:read"],
}

DEFAULT_USER_ROLE = "OPERATOR"
