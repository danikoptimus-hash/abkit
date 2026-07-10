"""POST /admin/db-connections/{id}/test (DB1): пробное SELECT 1 с понятной
классификацией ошибки. Классификация — best-effort по тексту исключения
(разные драйверы бросают разные классы) — точнее всего для PostgreSQL
(psycopg), для ClickHouse/MSSQL это разумное приближение, задокументированное
как известное ограничение (DB5, README).

dns_error и tcp_timeout — раньше были одной категорией host_unreachable
("Host unreachable or connection timed out"), из-за которой два РАЗНЫХ по
природе сбоя (неразрешимое имя хоста — опечатка в Host; и адрес резолвится,
но порт недоступен/сеть не пускает) показывались одним и тем же сообщением,
что затрудняло диагностику (ошибка находилась внутри одной ловушки-фразы,
"timeout" бралось голым словом и цепляло почти что угодно)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from abkit.db_connections.engines import ConnectionSpec, build_engine
from abkit.logging_config import get_logger

log = get_logger("abkit.db_connections.testing")

TestOutcome = Literal["ok", "dns_error", "tcp_timeout", "auth_failed", "db_not_found", "error"]


@dataclass
class ConnectionTestResult:
    outcome: TestOutcome
    message: str


def _classify(exc: Exception) -> ConnectionTestResult:
    text = str(exc).lower()
    if any(
        s in text
        for s in (
            "could not translate host", "name or service not known", "nodename nor servname",
            "failed to resolve host", "getaddrinfo failed", "no address associated with hostname",
            "temporary failure in name resolution",
        )
    ):
        return ConnectionTestResult("dns_error", "Could not resolve the host name — check the Host field for typos")
    if any(
        s in text
        for s in (
            "could not connect", "connection refused", "timeout expired", "connection timed out",
            "network is unreachable", "no route to host", "max retries exceeded", "operation timed out",
        )
    ):
        return ConnectionTestResult(
            "tcp_timeout", "Could not reach the host on this port — check Host/Port, firewall, or network access"
        )
    if any(
        s in text
        for s in (
            "password authentication failed", "authentication failed", "access denied",
            "login failed", "login incorrect", "auth_failed",
        )
    ):
        return ConnectionTestResult("auth_failed", "Authentication failed — check username/password")
    if any(
        s in text
        for s in ("unknown database", "cannot open database", 'database "') + (
            ("does not exist",) if "database" in text else ()
        )
    ):
        return ConnectionTestResult("db_not_found", "Database not found on the server")
    return ConnectionTestResult("error", str(exc)[:300])


def test_connection(spec: ConnectionSpec, timeout_sec: int = 10) -> ConnectionTestResult:
    log.info(
        "db_connection.test.start",
        engine=spec.engine, host=spec.host, port=spec.port, database=spec.database,
        username=spec.username, ssl=spec.ssl, timeout_sec=timeout_sec,
        # password деликатно НЕ логируется.
    )
    try:
        engine = build_engine(spec, timeout_sec=timeout_sec)
        try:
            with engine.connect() as conn:
                from sqlalchemy import text as sa_text

                conn.execute(sa_text("SELECT 1"))
            result = ConnectionTestResult("ok", "Connection successful")
        finally:
            engine.dispose()
    except Exception as e:  # noqa: BLE001 — классифицируем ниже, наружу течет только результат
        result = _classify(e)
        log.info(
            "db_connection.test.failed",
            engine=spec.engine, host=spec.host, port=spec.port, outcome=result.outcome,
            # Полный текст исключения — только в лог (для диагностики), не в
            # ответ API: может содержать детали инфраструктуры источника.
            exception=str(e)[:500],
        )
        return result
    log.info("db_connection.test.finish", engine=spec.engine, host=spec.host, port=spec.port, outcome="ok")
    return result
