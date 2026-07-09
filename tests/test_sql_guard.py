"""DB2 (CLAUDE.md dataset-from-SQL feature): SELECT-only validation before
any query is executed against an external DB."""

import pytest

from abkit.db_connections.sql_guard import SqlValidationError, validate_select_only


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1",
        "SELECT * FROM users",
        "WITH cte AS (SELECT 1 AS x) SELECT * FROM cte",
        "SELECT 1 UNION SELECT 2",
        "select   1 -- trailing comment",
    ],
)
def test_allows_select_and_cte_queries(sql):
    validate_select_only(sql, "postgresql")  # must not raise


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE users",
        "INSERT INTO users VALUES (1)",
        "UPDATE users SET role = 'admin'",
        "DELETE FROM users",
        "SELECT * FROM users; DROP TABLE users;--",
        "SELECT * FROM users FOR UPDATE",
        "WITH t AS (INSERT INTO users (email) VALUES ('x') RETURNING *) SELECT * FROM t",
        "",
    ],
)
def test_rejects_non_select_and_multi_statement_queries(sql):
    with pytest.raises(SqlValidationError):
        validate_select_only(sql, "postgresql")


def test_rejects_unparseable_sql():
    with pytest.raises(SqlValidationError):
        validate_select_only("SELEKT * FROM users !!!", "postgresql")
