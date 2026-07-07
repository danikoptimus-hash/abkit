"""Хеширование паролей (DOCKER.md §4.2): argon2id — основной алгоритм для
новых паролей; bcrypt verify — fallback для чтения уже существующих
bcrypt-хешей (например, при миграции пользователей из другой системы)."""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(plain: str) -> str:
    """Возвращает argon2id-хеш. Никогда не хранить/логировать сам plain."""
    return _hasher.hash(plain)


def verify_password(plain: str, password_hash: str) -> bool:
    """True, если plain соответствует хешу. Понимает и argon2 (основной путь),
    и bcrypt (fallback verify для унаследованных хешей)."""
    if password_hash.startswith("$argon2"):
        try:
            return _hasher.verify(password_hash, plain)
        except (VerifyMismatchError, InvalidHash):
            return False
    if password_hash.startswith(("$2a$", "$2b$", "$2y$")):
        import bcrypt

        try:
            return bcrypt.checkpw(plain.encode("utf-8"), password_hash.encode("utf-8"))
        except ValueError:
            return False
    return False
