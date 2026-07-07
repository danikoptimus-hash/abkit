"""Единая точка запуска мутирующих операций (design/analyze/validate/status
change/delete) — используется и Streamlit (app.py), и в перспективе CLI, чтобы
guard-проверки (DOCKER.md §4.1) применялись независимо от UI: Viewer не должен
суметь вызвать мутацию даже прямым вызовом этих функций, в обход спрятанных в
UI кнопок (критерий готовности этапа D2, DOCKER.md §12).

Аудит-лог и тайминги — этап D3 (DOCKER.md §8, пункт 4); здесь только guard'ы.
Эти функции осмысленны только в серверном режиме (ABKIT_MODE=db) — в файловом
режиме нет модели пользователей/ролей, и app.py их не вызывает.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from abkit.analysis.results import AnalysisResults
from abkit.auth.guards import CurrentUser, require_owner_or_admin, require_role
from abkit.config import DesignConfig
from abkit.experiment import Experiment


def _get_owner_id(name: str) -> str:
    from abkit import storage
    from abkit.db.repositories import ExperimentRepo

    exp_row = ExperimentRepo().get_by_name(name)
    if exp_row is None:
        raise storage.StorageError(f"Эксперимент '{name}' не найден")
    return str(exp_row.owner_id)


def run_design(
    current_user: CurrentUser, config: DesignConfig, data: pd.DataFrame, **kwargs: Any
) -> Experiment:
    """Создавать эксперименты может Editor+ (DOCKER.md §4.1)."""
    require_role(current_user, "editor")
    return Experiment.design(config, data, owner_id=current_user.id, **kwargs)


def run_analyze(
    current_user: CurrentUser, experiment: Experiment, data: pd.DataFrame, **kwargs: Any
) -> AnalysisResults:
    """Запускать Analyze может Editor+ — на любом эксперименте, не только своем
    (DOCKER.md §4.1: у этого права нет разделения "свои/чужие", в отличие от
    смены статуса)."""
    require_role(current_user, "editor")
    return experiment.analyze(data, **kwargs)


def run_validate_aa(current_user: CurrentUser, *args: Any, **kwargs: Any):
    require_role(current_user, "editor")
    from abkit.validation.simulation import run_aa

    return run_aa(*args, **kwargs)


def run_validate_ab(current_user: CurrentUser, *args: Any, **kwargs: Any):
    require_role(current_user, "editor")
    from abkit.validation.simulation import run_ab

    return run_ab(*args, **kwargs)


def run_update_status(current_user: CurrentUser, name: str, new_status: str) -> None:
    """Менять статус СВОИХ экспериментов может Editor, ЛЮБЫХ — Admin (DOCKER.md §4.1)."""
    from abkit.db.repositories import ExperimentRepo

    owner_id = _get_owner_id(name)
    require_owner_or_admin(current_user, owner_id)
    ExperimentRepo().update_status(name, new_status)


def run_delete_experiment(current_user: CurrentUser, name: str) -> None:
    """Удалять эксперименты может только Admin (DOCKER.md §4.1) — без исключения
    "свои", в отличие от смены статуса."""
    require_role(current_user, "admin")

    import shutil

    from abkit.db.repositories import ExperimentRepo
    from abkit.db.store import DbExperimentStore

    ExperimentRepo().delete(name)
    artifact_dir = DbExperimentStore().data_dir / name
    if artifact_dir.exists():
        shutil.rmtree(artifact_dir)
