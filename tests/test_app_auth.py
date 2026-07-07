"""AppTest-сценарий логин -> design -> logout (ABKIT_MODE=db) — критерий
готовности этапа D2 (DOCKER.md §12). Файловый режим (ABKIT_MODE не задан)
по-прежнему не показывает логин-экран вообще — см. tests/test_app.py, там
current_user всегда None и поведение не изменилось."""

from streamlit.testing.v1 import AppTest

from abkit.auth.passwords import hash_password


def _fresh_db_app(db_url, tmp_path, monkeypatch) -> AppTest:
    monkeypatch.setenv("ABKIT_MODE", "db")
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("ABKIT_SECRET_KEY", "a-real-generated-secret-for-apptest-scenario")
    monkeypatch.setenv("ABKIT_DATA_DIR", str(tmp_path / "data"))
    # _next_demo_name()/storage.get_experiments_dir() читают файловый registry.json
    # независимо от ABKIT_MODE (это file-mode-only хелпер) — без изоляции тест
    # словил бы коллизию имени "demo" с реальным ~/ab_experiments на машине.
    monkeypatch.setenv("ABKIT_EXPERIMENTS_DIR", str(tmp_path / "file_side"))
    at = AppTest.from_file("app.py")
    at.run(timeout=30)
    return at


def test_unauthenticated_user_sees_only_login_form(db_url, tmp_path, monkeypatch):
    at = _fresh_db_app(db_url, tmp_path, monkeypatch)
    assert not at.exception
    assert any("вход" in t.value.lower() for t in at.title)
    assert any(ti.label == "Email" for ti in at.text_input)
    assert any(ti.label == "Пароль" for ti in at.text_input)
    # никаких табов/данных экспериментов не рендерится до входа
    assert len(at.tabs) == 0


def test_login_with_wrong_password_shows_error_and_stays_on_login(db_url, tmp_path, monkeypatch):
    from abkit.db.repositories import UserRepo

    UserRepo().create(
        email="viewer@co.com", name="Viewer", password_hash=hash_password("realpw123"), role="viewer"
    )
    at = _fresh_db_app(db_url, tmp_path, monkeypatch)

    next(ti for ti in at.text_input if ti.label == "Email").set_value("viewer@co.com")
    next(ti for ti in at.text_input if ti.label == "Пароль").set_value("wrongpw")
    at.button[0].click().run(timeout=30)

    assert not at.exception
    assert any("Неверный" in e.value for e in at.error)
    assert len(at.tabs) == 0


def test_login_design_logout_scenario(db_url, tmp_path, monkeypatch):
    """Полный сценарий: Editor логинится, дизайнит demo-эксперимент через UI,
    видит его сводку, разлогинивается — снова видит только форму входа."""
    from abkit.db.repositories import UserRepo

    UserRepo().create(
        email="editor@co.com", name="Editor", password_hash=hash_password("pw12345"), role="editor"
    )

    at = _fresh_db_app(db_url, tmp_path, monkeypatch)

    next(ti for ti in at.text_input if ti.label == "Email").set_value("editor@co.com")
    next(ti for ti in at.text_input if ti.label == "Пароль").set_value("pw12345")
    at.button[0].click().run(timeout=30)

    assert not at.exception
    assert len(at.tabs) == 4  # Design/Analyze/Experiments/Validation, без Admin (editor)
    assert any("editor@co.com" in c.value for c in at.sidebar.caption)

    design_tab = at.tabs[0]
    next(b for b in design_tab.button if "демо-данные" in b.label).click().run(timeout=30)
    assert not at.exception

    design_tab = at.tabs[0]
    next(b for b in design_tab.button if "Спроектировать" in b.label).click().run(timeout=30)
    assert not at.exception

    design_tab = at.tabs[0]
    assert any("Сводка: demo" in s.value for s in design_tab.subheader)

    from abkit.db.repositories import ExperimentRepo

    exp_row = ExperimentRepo().get_by_name("demo")
    assert exp_row is not None

    at.sidebar.button[0].click().run(timeout=30)  # "Выйти"
    assert not at.exception
    assert any(ti.label == "Email" for ti in at.text_input)
    assert len(at.tabs) == 0


def test_viewer_does_not_see_design_form_after_login(db_url, tmp_path, monkeypatch):
    from abkit.db.repositories import UserRepo

    UserRepo().create(
        email="viewer2@co.com", name="Viewer2", password_hash=hash_password("pw12345"), role="viewer"
    )
    at = _fresh_db_app(db_url, tmp_path, monkeypatch)

    next(ti for ti in at.text_input if ti.label == "Email").set_value("viewer2@co.com")
    next(ti for ti in at.text_input if ti.label == "Пароль").set_value("pw12345")
    at.button[0].click().run(timeout=30)

    assert not at.exception
    design_tab = at.tabs[0]
    assert any("Недостаточно прав" in i.value for i in design_tab.info)
    assert not any("демо-данные" in b.label for b in design_tab.button)


def test_admin_sees_admin_tab_editor_does_not(db_url, tmp_path, monkeypatch):
    from abkit.db.repositories import UserRepo

    UserRepo().create(
        email="admin2@co.com", name="Admin2", password_hash=hash_password("pw12345"), role="admin"
    )
    at = _fresh_db_app(db_url, tmp_path, monkeypatch)

    next(ti for ti in at.text_input if ti.label == "Email").set_value("admin2@co.com")
    next(ti for ti in at.text_input if ti.label == "Пароль").set_value("pw12345")
    at.button[0].click().run(timeout=30)

    assert not at.exception
    assert len(at.tabs) == 5  # + Admin
    admin_tab = at.tabs[4]
    assert any("Администрирование" in h.value for h in admin_tab.header)
