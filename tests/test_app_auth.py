"""AppTest-сценарий логин -> design -> logout (ABKIT_MODE=db) — критерий
готовности этапа D2 (DOCKER.md §12). Файловый режим (ABKIT_MODE не задан)
по-прежнему не показывает логин-экран вообще — см. tests/test_app.py, там
current_user всегда None и поведение не изменилось."""

import pandas as pd
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


def test_experiments_tab_history_and_admin_audit_show_design_event(db_url, tmp_path, monkeypatch):
    """DOCKER.md §6.2: «История» — события эксперимента видны любой роли;
    «Аудит» у Admin — общий список событий."""
    from abkit.db.repositories import UserRepo

    UserRepo().create(
        email="admin3@co.com", name="Admin3", password_hash=hash_password("pw12345"), role="admin"
    )
    at = _fresh_db_app(db_url, tmp_path, monkeypatch)

    next(ti for ti in at.text_input if ti.label == "Email").set_value("admin3@co.com")
    next(ti for ti in at.text_input if ti.label == "Пароль").set_value("pw12345")
    at.button[0].click().run(timeout=30)

    design_tab = at.tabs[0]
    next(b for b in design_tab.button if "демо-данные" in b.label).click().run(timeout=30)
    design_tab = at.tabs[0]
    next(b for b in design_tab.button if "Спроектировать" in b.label).click().run(timeout=30)
    assert not at.exception

    experiments_tab = at.tabs[2]
    history_expanders = [e for e in experiments_tab.expander if e.label == "История"]
    assert len(history_expanders) == 1
    history_dfs = history_expanders[0].dataframe
    assert len(history_dfs) == 1
    assert "experiment.create" in history_dfs[0].value["действие"].values

    admin_tab = at.tabs[4]
    assert any("Аудит" in s.value for s in admin_tab.subheader)
    audit_dfs = admin_tab.dataframe
    all_actions = pd.concat([df.value["действие"] for df in audit_dfs if "действие" in df.value.columns])
    assert "experiment.create" in all_actions.values


def test_imported_legacy_experiment_visible_in_ui_with_status_and_report(db_url, tmp_path, monkeypatch):
    """Критерий готовности этапа D5 (DOCKER.md §12): "эксперименты видны в UI
    со статусами и отчетами" после import-legacy."""
    import numpy as np

    from abkit.config import DesignConfig, MetricConfig
    from abkit.db.import_legacy import import_legacy_dir
    from abkit.db.repositories import UserRepo
    from abkit.experiment import Experiment

    # строим настоящий файловый (легаси) эксперимент с анализом и отчетом
    legacy_dir = tmp_path / "legacy_source"
    rng = np.random.default_rng(0)
    n = 200
    data = pd.DataFrame(
        {
            "user_id": [f"u{i}" for i in range(n)],
            "revenue": rng.normal(100, 20, size=n),
        }
    )
    config = DesignConfig(
        name="imported_exp",
        unit_col="user_id",
        groups={"control": 0.5, "treatment": 0.5},
        metrics=[MetricConfig(name="revenue", type="continuous")],
        sample_size=n,
        split_method="simple",
        seed=1,
    )
    legacy_experiment = Experiment.design(config, data, experiments_dir=legacy_dir)
    post_data = pd.DataFrame(
        {
            "user_id": legacy_experiment.assignments["unit_id"],
            "revenue": rng.normal(100, 20, size=n),
        }
    )
    legacy_experiment.analyze(post_data).report()

    monkeypatch.setenv("ABKIT_MODE", "db")
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("ABKIT_SECRET_KEY", "a-real-generated-secret-for-import-ui-test")
    monkeypatch.setenv("ABKIT_DATA_DIR", str(tmp_path / "server_data"))

    UserRepo().create(
        email="importadmin@co.com", name="ImportAdmin", password_hash=hash_password("pw12345"), role="admin"
    )
    result = import_legacy_dir(legacy_dir, "importadmin@co.com")
    assert result.imported == ["imported_exp"]

    at = AppTest.from_file("app.py")
    at.run(timeout=30)
    next(ti for ti in at.text_input if ti.label == "Email").set_value("importadmin@co.com")
    next(ti for ti in at.text_input if ti.label == "Пароль").set_value("pw12345")
    at.button[0].click().run(timeout=30)
    assert not at.exception

    experiments_tab = at.tabs[2]
    registry_dfs = experiments_tab.dataframe
    assert len(registry_dfs) >= 1
    registry_df = registry_dfs[0].value
    assert "imported_exp" in registry_df["эксперимент"].values
    row = registry_df[registry_df["эксперимент"] == "imported_exp"].iloc[0]
    assert row["status"] == "designed"

    exp_select = next(s for s in experiments_tab.selectbox if s.key == "exp_status_select")
    exp_select.set_value("imported_exp").run(timeout=30)
    experiments_tab = at.tabs[2]
    assert not at.exception

    report_radio = next(r for r in experiments_tab.radio if r.key == "exp_report_choice")
    report_radio.set_value("report.html").run(timeout=30)
    experiments_tab = at.tabs[2]
    assert not at.exception
    assert not any("еще не создан" in i.value for i in experiments_tab.info)
