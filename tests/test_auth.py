"""abkit/auth/: хеширование паролей, JWT-токены сессии, guard-функции,
оркестрация логина/пользователей (DOCKER.md §4). Критерий готовности этапа D2:
rate-limit работает, матрица прав из §4.1 покрыта тестами."""

import pytest

from abkit.auth.guards import AuthError, CurrentUser, require_admin, require_owner_or_admin, require_role
from abkit.auth.passwords import hash_password, verify_password
from abkit.auth.tokens import TokenError, create_session_token, verify_session_token


# --------------------------------------------------------------------------
# passwords.py
# --------------------------------------------------------------------------


def test_hash_password_produces_argon2_hash():
    h = hash_password("correct horse battery staple")
    assert h.startswith("$argon2")


def test_verify_password_roundtrip():
    h = hash_password("s3cret!")
    assert verify_password("s3cret!", h) is True
    assert verify_password("wrong", h) is False


def test_verify_password_bcrypt_fallback():
    import bcrypt

    bcrypt_hash = bcrypt.hashpw(b"legacy-pw", bcrypt.gensalt()).decode("ascii")
    assert verify_password("legacy-pw", bcrypt_hash) is True
    assert verify_password("wrong", bcrypt_hash) is False


def test_verify_password_unknown_format_returns_false():
    assert verify_password("anything", "not-a-real-hash") is False


# --------------------------------------------------------------------------
# tokens.py
# --------------------------------------------------------------------------

_SECRET = "test-secret-key-not-a-default-0123456789"


def test_create_and_verify_session_token_roundtrip():
    token = create_session_token(
        user_id="u1", email="a@co.com", role="editor", lifetime_hours=1, secret_key=_SECRET
    )
    payload = verify_session_token(token, secret_key=_SECRET)
    assert payload["sub"] == "u1"
    assert payload["email"] == "a@co.com"
    assert payload["role"] == "editor"


def test_verify_session_token_expired_raises():
    token = create_session_token(
        user_id="u1", email="a@co.com", role="viewer", lifetime_hours=-1, secret_key=_SECRET
    )
    with pytest.raises(TokenError, match="истекл"):
        verify_session_token(token, secret_key=_SECRET)


def test_verify_session_token_wrong_secret_raises():
    token = create_session_token(
        user_id="u1", email="a@co.com", role="viewer", lifetime_hours=1, secret_key=_SECRET
    )
    with pytest.raises(TokenError, match="Невалидный"):
        verify_session_token(token, secret_key="a-different-secret")


def test_get_secret_key_missing_raises(monkeypatch):
    from abkit.auth.tokens import get_secret_key

    monkeypatch.delenv("ABKIT_SECRET_KEY", raising=False)
    with pytest.raises(TokenError, match="не задан"):
        get_secret_key()


def test_get_secret_key_default_value_raises(monkeypatch):
    from abkit.auth.tokens import get_secret_key

    monkeypatch.setenv("ABKIT_SECRET_KEY", "change-me-long-random-string")
    with pytest.raises(TokenError, match="дефолтное значение"):
        get_secret_key()


def test_get_secret_key_valid_value_ok(monkeypatch):
    from abkit.auth.tokens import get_secret_key

    monkeypatch.setenv("ABKIT_SECRET_KEY", "a-real-generated-secret")
    assert get_secret_key() == "a-real-generated-secret"


# --------------------------------------------------------------------------
# guards.py — матрица прав DOCKER.md §4.1
# --------------------------------------------------------------------------


def _user(role, uid="u1"):
    return CurrentUser(id=uid, email=f"{uid}@co.com", name="N", role=role)


def test_require_login_raises_on_none():
    with pytest.raises(AuthError, match="Требуется вход"):
        require_role(None, "viewer")


@pytest.mark.parametrize(
    "role,min_role,should_pass",
    [
        ("viewer", "viewer", True),
        ("viewer", "editor", False),
        ("viewer", "admin", False),
        ("editor", "viewer", True),
        ("editor", "editor", True),
        ("editor", "admin", False),
        ("admin", "viewer", True),
        ("admin", "editor", True),
        ("admin", "admin", True),
    ],
)
def test_require_role_matrix(role, min_role, should_pass):
    user = _user(role)
    if should_pass:
        assert require_role(user, min_role) is user
    else:
        with pytest.raises(AuthError, match="Недостаточно прав"):
            require_role(user, min_role)


def test_require_owner_or_admin_viewer_always_blocked():
    with pytest.raises(AuthError):
        require_owner_or_admin(_user("viewer", "u1"), "u1")


def test_require_owner_or_admin_editor_own_experiment_ok():
    user = _user("editor", "u1")
    assert require_owner_or_admin(user, "u1") is user


def test_require_owner_or_admin_editor_others_experiment_blocked():
    with pytest.raises(AuthError, match="только свои"):
        require_owner_or_admin(_user("editor", "u1"), "u2")


def test_require_owner_or_admin_admin_any_experiment_ok():
    user = _user("admin", "u1")
    assert require_owner_or_admin(user, "someone-else") is user


def test_require_admin_blocks_editor():
    with pytest.raises(AuthError):
        require_admin(_user("editor"))


def test_require_admin_allows_admin():
    user = _user("admin")
    assert require_admin(user) is user


# --------------------------------------------------------------------------
# service.py — оркестрация логина/пользователей (нужен Postgres)
# --------------------------------------------------------------------------


@pytest.fixture
def auth_env(db_url, tmp_path, monkeypatch):
    monkeypatch.setenv("ABKIT_SECRET_KEY", "a-real-generated-secret-for-tests")
    monkeypatch.setenv("ABKIT_DATA_DIR", str(tmp_path))
    yield


def test_login_success_returns_valid_token(auth_env):
    from abkit.auth.passwords import hash_password
    from abkit.auth.service import current_user_from_token, login
    from abkit.db.repositories import UserRepo

    UserRepo().create(
        email="editor@co.com", name="Ed", password_hash=hash_password("pw12345"), role="editor"
    )

    token = login("editor@co.com", "pw12345")
    user = current_user_from_token(token)
    assert user is not None
    assert user.email == "editor@co.com"
    assert user.role == "editor"


def test_login_wrong_password_raises(auth_env):
    from abkit.auth.passwords import hash_password
    from abkit.auth.service import login
    from abkit.db.repositories import UserRepo

    UserRepo().create(email="u2@co.com", name="U2", password_hash=hash_password("correctpw"), role="viewer")

    with pytest.raises(AuthError, match="Неверный"):
        login("u2@co.com", "wrongpw")


def test_login_unknown_email_raises(auth_env):
    from abkit.auth.service import login

    with pytest.raises(AuthError, match="Неверный"):
        login("nobody@co.com", "whatever")


def test_login_rate_limit_locks_after_5_failures(auth_env):
    """DOCKER.md §4.2: 5 неудачных попыток подряд -> блокировка на 15 минут."""
    from abkit.auth.passwords import hash_password
    from abkit.auth.service import login
    from abkit.db.repositories import UserRepo

    UserRepo().create(
        email="brute@co.com", name="B", password_hash=hash_password("realpw"), role="viewer"
    )

    for _ in range(5):
        with pytest.raises(AuthError, match="Неверный"):
            login("brute@co.com", "wrongpw")

    # 6-я попытка — даже с ПРАВИЛЬНЫМ паролем должна быть заблокирована
    with pytest.raises(AuthError, match="Слишком много"):
        login("brute@co.com", "realpw")


def test_login_deactivated_user_raises(auth_env):
    from abkit.auth.passwords import hash_password
    from abkit.auth.service import admin_set_active, login
    from abkit.db.repositories import UserRepo

    UserRepo().create(
        email="blocked@co.com", name="Bl", password_hash=hash_password("pw"), role="viewer"
    )
    admin_set_active(_user("admin", "admin-id"), target_email="blocked@co.com", is_active=False)

    with pytest.raises(AuthError, match="заблокирован"):
        login("blocked@co.com", "pw")


def test_current_user_from_token_none_for_empty_or_invalid(auth_env):
    from abkit.auth.service import current_user_from_token

    assert current_user_from_token(None) is None
    assert current_user_from_token("") is None
    assert current_user_from_token("not-a-jwt") is None


def test_change_own_password_wrong_old_password_raises(auth_env):
    from abkit.auth.passwords import hash_password
    from abkit.auth.service import change_own_password
    from abkit.db.repositories import UserRepo

    user_id = UserRepo().create(
        email="chg@co.com", name="C", password_hash=hash_password("oldpw"), role="viewer"
    )
    current = CurrentUser(id=str(user_id), email="chg@co.com", name="C", role="viewer")
    with pytest.raises(AuthError, match="неверен"):
        change_own_password(current, "notoldpw", "newpw12345")


def test_change_own_password_success_allows_new_login(auth_env):
    from abkit.auth.passwords import hash_password
    from abkit.auth.service import change_own_password, login
    from abkit.db.repositories import UserRepo

    user_id = UserRepo().create(
        email="chg2@co.com", name="C2", password_hash=hash_password("oldpw123"), role="viewer"
    )
    current = CurrentUser(id=str(user_id), email="chg2@co.com", name="C2", role="viewer")
    change_own_password(current, "oldpw123", "newpw456")

    token = login("chg2@co.com", "newpw456")
    assert token is not None
    with pytest.raises(AuthError):
        login("chg2@co.com", "oldpw123")


def test_admin_create_user_requires_admin_when_acting_user_given(auth_env):
    from abkit.auth.service import admin_create_user

    with pytest.raises(AuthError):
        admin_create_user(_user("editor"), email="x@co.com", name="X", role="viewer")


def test_admin_create_user_bypasses_check_when_acting_user_none(auth_env):
    """CLI abkit-admin (доверенный, запускается внутри контейнера) не проверяет права."""
    from abkit.auth.service import admin_create_user

    user_id, generated = admin_create_user(None, email="cli-created@co.com", name="CLI", role="admin")
    assert user_id
    assert generated


def test_admin_create_user_generates_password_and_sets_must_change(auth_env):
    from abkit.auth.service import admin_create_user
    from abkit.db.repositories import UserRepo

    user_id, generated = admin_create_user(None, email="gen@co.com", name="G", role="viewer")
    assert len(generated) > 8
    user = UserRepo().get_by_id(__import__("uuid").UUID(user_id))
    assert user.must_change_password is True


def test_admin_reset_password_requires_admin(auth_env):
    from abkit.auth.service import admin_create_user, admin_reset_password

    admin_create_user(None, email="target@co.com", name="T", role="viewer", password="initialpw")
    with pytest.raises(AuthError):
        admin_reset_password(_user("editor"), target_email="target@co.com")


def test_admin_reset_password_unknown_user_raises(auth_env):
    from abkit.auth.service import admin_reset_password

    with pytest.raises(AuthError, match="не найден"):
        admin_reset_password(None, target_email="nobody@co.com")


def test_self_register_disabled_by_default(auth_env, monkeypatch):
    from abkit.auth.service import self_register

    monkeypatch.delenv("ABKIT_ALLOW_SELF_REGISTRATION", raising=False)
    with pytest.raises(AuthError, match="отключена"):
        self_register(email="new@co.com", name="New", password="pw12345")


def test_self_register_enabled_creates_viewer(auth_env, monkeypatch):
    from abkit.auth.service import self_register
    from abkit.db.repositories import UserRepo

    monkeypatch.setenv("ABKIT_ALLOW_SELF_REGISTRATION", "true")
    user_id = self_register(email="selfreg@co.com", name="Self", password="pw12345")
    user = UserRepo().get_by_id(__import__("uuid").UUID(user_id))
    assert user.role == "viewer"
