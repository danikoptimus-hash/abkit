"""abkit._read_version() (item 8, audit-details+ package): version is
sourced from ABKIT_VERSION (set at Docker build time on a tagged CI build)
or, failing that, a GIT_SHA file baked in by docker/Dockerfile's `version`
build stage — never a hardcoded string that goes stale across releases."""

from __future__ import annotations

from abkit import _read_version


def test_explicit_tag_version_wins_over_git_sha(tmp_path):
    sha_file = tmp_path / "GIT_SHA"
    sha_file.write_text("abc1234")
    assert _read_version(env={"ABKIT_VERSION": "2.5.0"}, sha_file=sha_file) == "2.5.0"


def test_explicit_tag_version_strips_leading_v(tmp_path):
    assert _read_version(env={"ABKIT_VERSION": "v2.5.0"}, sha_file=tmp_path / "GIT_SHA") == "2.5.0"


def test_local_build_falls_back_to_git_sha(tmp_path):
    sha_file = tmp_path / "GIT_SHA"
    sha_file.write_text("2684699\n")
    assert _read_version(env={}, sha_file=sha_file) == "dev (2684699)"


def test_local_build_with_unknown_sha_falls_back_to_plain_dev(tmp_path):
    sha_file = tmp_path / "GIT_SHA"
    sha_file.write_text("unknown")
    assert _read_version(env={}, sha_file=sha_file) == "dev"


def test_local_build_with_no_git_sha_file_falls_back_to_plain_dev(tmp_path):
    assert _read_version(env={}, sha_file=tmp_path / "GIT_SHA") == "dev"


def test_explicit_dev_env_value_is_treated_as_unset(tmp_path):
    sha_file = tmp_path / "GIT_SHA"
    sha_file.write_text("abc1234")
    assert _read_version(env={"ABKIT_VERSION": "dev"}, sha_file=sha_file) == "dev (abc1234)"
