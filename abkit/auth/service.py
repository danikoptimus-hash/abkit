"""Оркестрация логина/пользователей: связывает UserRepo (D1) + passwords +
tokens + guards. Единая точка входа для app.py и cli_admin.py."""

from __future__ import annotations

import os
import secrets
import uuid as uuid_mod
from datetime import datetime, timezone

from abkit.auth.guards import AuthError, CurrentUser, require_admin
from abkit.auth.passwords import hash_password, verify_password
from abkit.auth.tokens import TokenError, create_session_token, verify_session_token
from abkit.db.repositories import UserRepo

_MAX_LOGIN_ATTEMPTS = 5
_LOCKOUT_MINUTES = 15


def _session_lifetime_hours() -> float:
    return float(os.environ.get("ABKIT_SESSION_LIFETIME_HOURS", "72"))


def login(email: str, password: str) -> str:
    """Возвращает токен сессии при успехе; бросает AuthError иначе.

    Блокировка перебора (DOCKER.md §4.2): 5 неудачных попыток подряд -> 15 минут
    блокировки для этого email, хранится в БД (UserRepo.record_login_failure),
    не в памяти процесса — переживает рестарт/несколько воркеров.
    """
    repo = UserRepo()
    user = repo.get_by_email(email)
    if user is None:
        raise AuthError("Неверный email или пароль")

    if user.locked_until is not None and user.locked_until > datetime.now(timezone.utc):
        raise AuthError(
            f"Слишком много неудачных попыток входа. Повторите после "
            f"{user.locked_until.strftime('%H:%M UTC')}"
        )

    if not user.is_active:
        raise AuthError("Учетная запись заблокирована администратором")

    if not verify_password(password, user.password_hash):
        repo.record_login_failure(email, max_attempts=_MAX_LOGIN_ATTEMPTS, lockout_minutes=_LOCKOUT_MINUTES)
        raise AuthError("Неверный email или пароль")

    repo.record_login_success(user.id)
    return create_session_token(
        user_id=str(user.id),
        email=user.email,
        role=user.role,
        lifetime_hours=_session_lifetime_hours(),
    )


def current_user_from_token(token: str | None) -> CurrentUser | None:
    """None, если токена нет/невалиден/юзер деактивирован — вызывающая сторона
    (app.py) в этом случае должна показать экран логина."""
    if not token:
        return None
    try:
        payload = verify_session_token(token)
    except TokenError:
        return None
    try:
        user_id = uuid_mod.UUID(payload["sub"])
    except (KeyError, ValueError):
        return None
    user = UserRepo().get_by_id(user_id)
    if user is None or not user.is_active:
        return None
    return CurrentUser(
        id=str(user.id),
        email=user.email,
        name=user.name,
        role=user.role,
        must_change_password=user.must_change_password,
    )


def change_own_password(current_user: CurrentUser, old_password: str, new_password: str) -> None:
    repo = UserRepo()
    user = repo.get_by_id(uuid_mod.UUID(current_user.id))
    if user is None or not verify_password(old_password, user.password_hash):
        raise AuthError("Текущий пароль неверен")
    repo.set_password_hash(user.id, hash_password(new_password), must_change_password=False)


def _generate_temp_password() -> str:
    return secrets.token_urlsafe(12)


def admin_create_user(
    acting_user: CurrentUser | None,
    *,
    email: str,
    name: str,
    role: str,
    password: str | None = None,
) -> tuple[str, str]:
    """acting_user=None допустим только для доверенного CLI (abkit-admin,
    запущенного внутри контейнера) — bootstrap первого админа именно так и
    происходит (аналог `superset fab create-admin`). Из UI acting_user всегда
    передается и должен быть Admin."""
    if acting_user is not None:
        require_admin(acting_user)
    generated = password or _generate_temp_password()
    user_id = UserRepo().create(
        email=email,
        name=name,
        password_hash=hash_password(generated),
        role=role,
        must_change_password=password is None,
    )
    return str(user_id), generated


def admin_reset_password(
    acting_user: CurrentUser | None, *, target_email: str, new_password: str | None = None
) -> str:
    if acting_user is not None:
        require_admin(acting_user)
    user = UserRepo().get_by_email(target_email)
    if user is None:
        raise AuthError(f"Пользователь '{target_email}' не найден")
    generated = new_password or _generate_temp_password()
    UserRepo().set_password_hash(user.id, hash_password(generated), must_change_password=True)
    return generated


def admin_set_role(acting_user: CurrentUser, *, target_email: str, role: str) -> None:
    require_admin(acting_user)
    user = UserRepo().get_by_email(target_email)
    if user is None:
        raise AuthError(f"Пользователь '{target_email}' не найден")
    UserRepo().update_role(user.id, role)


def admin_set_active(acting_user: CurrentUser, *, target_email: str, is_active: bool) -> None:
    require_admin(acting_user)
    user = UserRepo().get_by_email(target_email)
    if user is None:
        raise AuthError(f"Пользователь '{target_email}' не найден")
    UserRepo().set_active(user.id, is_active)


def self_register(*, email: str, name: str, password: str) -> str:
    """DOCKER.md §4.2: ABKIT_ALLOW_SELF_REGISTRATION=true включает страницу
    самостоятельной регистрации, новый пользователь получает роль Viewer."""
    if os.environ.get("ABKIT_ALLOW_SELF_REGISTRATION", "false").lower() != "true":
        raise AuthError("Самостоятельная регистрация отключена")
    user_id = UserRepo().create(email=email, name=name, password_hash=hash_password(password), role="viewer")
    return str(user_id)
