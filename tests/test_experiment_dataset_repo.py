"""DB3 (CLAUDE.md dataset-centric model): ExperimentDatasetRepo — the
many-to-many use record between experiments and datasets."""

from __future__ import annotations

from abkit.auth.passwords import hash_password
from abkit.db.repositories import DatasetRepo, ExperimentDatasetRepo, ExperimentRepo, UserRepo


def _make_experiment_and_dataset(name="exp_a"):
    owner_id = UserRepo().create(
        email=f"owner_{name}@co.com", first_name="O", password_hash=hash_password("pw12345"), role="editor",
    )
    exp = ExperimentRepo().create(
        name=name, owner_id=owner_id, status="designed",
        config={"name": name, "unit_col": "user_id", "groups": {"control": 0.5, "treatment": 0.5}},
    )
    dataset_id = DatasetRepo().create(
        kind="pre_design", filename="d.csv", n_rows=10, columns=["user_id"],
        storage_path="/tmp/d.csv", sha256="abc", source="upload",
    )
    return exp.id, dataset_id


def test_link_is_idempotent(db_url):
    exp_id, dataset_id = _make_experiment_and_dataset()
    repo = ExperimentDatasetRepo()
    repo.link(exp_id, dataset_id, kind="pre_design")
    repo.link(exp_id, dataset_id, kind="pre_design")  # same triple again
    rows = repo.list_for_experiment(exp_id)
    assert len(rows) == 1
    assert rows[0].kind == "pre_design"


def test_same_dataset_can_be_linked_with_different_kinds(db_url):
    exp_id, dataset_id = _make_experiment_and_dataset()
    repo = ExperimentDatasetRepo()
    repo.link(exp_id, dataset_id, kind="pre_design")
    repo.link(exp_id, dataset_id, kind="post_analysis")
    rows = repo.list_for_experiment(exp_id)
    assert {r.kind for r in rows} == {"pre_design", "post_analysis"}


def test_same_dataset_can_be_linked_to_multiple_experiments(db_url):
    exp_a, dataset_id = _make_experiment_and_dataset("exp_a")
    exp_b, _ = _make_experiment_and_dataset("exp_b")
    repo = ExperimentDatasetRepo()
    repo.link(exp_a, dataset_id, kind="pre_design")
    repo.link(exp_b, dataset_id, kind="post_analysis")
    assert len(repo.list_for_experiment(exp_a)) == 1
    assert len(repo.list_for_experiment(exp_b)) == 1
