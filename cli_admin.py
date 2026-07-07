"""CLI abkit-admin: управление пользователями серверного режима (ABKIT_MODE=db,
требует DATABASE_URL) — DOCKER.md §4.3. Аналог `superset fab create-admin`:
команды не требуют вошедшего пользователя — доверенная операция (запускается
внутри контейнера, `docker compose exec app abkit-admin ...`)."""

from __future__ import annotations

import sys

import typer
from rich.console import Console
from rich.table import Table

from abkit.auth.guards import AuthError
from abkit.auth.service import admin_create_user, admin_reset_password
from abkit.db.repositories import UserRepo

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

app = typer.Typer(add_completion=False, help="abkit-admin — управление пользователями (ABKIT_MODE=db)")
console = Console(legacy_windows=False)

_ROLES = ("viewer", "editor", "admin")


@app.command("create-admin")
def create_admin(
    email: str = typer.Option(..., "--email"),
    name: str = typer.Option("Admin", "--name"),
    password: str = typer.Option(None, "--password"),
) -> None:
    """Создает первого администратора (bootstrap для полностью автоматического деплоя)."""
    try:
        user_id, generated = admin_create_user(
            None, email=email, name=name, role="admin", password=password
        )
    except AuthError as e:
        console.print(f"[red]Ошибка:[/red] {e}")
        raise typer.Exit(code=1)
    console.print(f"[green]Администратор создан:[/green] {email} (id={user_id})")
    if password is None:
        console.print(f"Временный пароль (сохраните — показывается один раз): [bold]{generated}[/bold]")


@app.command("create-user")
def create_user(
    email: str = typer.Option(..., "--email"),
    role: str = typer.Option(..., "--role"),
    name: str = typer.Option("", "--name"),
    password: str = typer.Option(None, "--password"),
) -> None:
    if role not in _ROLES:
        console.print(f"[red]Ошибка:[/red] неизвестная роль '{role}'. Допустимые: {', '.join(_ROLES)}")
        raise typer.Exit(code=1)
    try:
        user_id, generated = admin_create_user(
            None, email=email, name=name or email, role=role, password=password
        )
    except AuthError as e:
        console.print(f"[red]Ошибка:[/red] {e}")
        raise typer.Exit(code=1)
    console.print(f"[green]Пользователь создан:[/green] {email} (роль={role}, id={user_id})")
    if password is None:
        console.print(f"Временный пароль: [bold]{generated}[/bold]")


@app.command("reset-password")
def reset_password(
    email: str = typer.Option(..., "--email"),
    password: str = typer.Option(None, "--password"),
) -> None:
    try:
        generated = admin_reset_password(None, target_email=email, new_password=password)
    except AuthError as e:
        console.print(f"[red]Ошибка:[/red] {e}")
        raise typer.Exit(code=1)
    console.print(f"[green]Пароль сброшен для[/green] {email}")
    if password is None:
        console.print(f"Временный пароль: [bold]{generated}[/bold]")


@app.command("list-users")
def list_users() -> None:
    users = UserRepo().list_all()
    table = Table(title="Пользователи abkit")
    table.add_column("Email")
    table.add_column("Имя")
    table.add_column("Роль")
    table.add_column("Активен")
    table.add_column("Создан")
    table.add_column("Последний вход")
    for u in users:
        table.add_row(
            u.email,
            u.name,
            u.role,
            "да" if u.is_active else "нет",
            u.created_at.strftime("%Y-%m-%d %H:%M") if u.created_at else "-",
            u.last_login_at.strftime("%Y-%m-%d %H:%M") if u.last_login_at else "-",
        )
    console.print(table)


@app.command("import-legacy")
def import_legacy(
    dir: str = typer.Option(..., "--dir", help="Папка со старым файловым реестром (registry.json + эксперименты)"),
    owner: str = typer.Option(..., "--owner", help="Email существующего пользователя — владелец импортированных экспериментов"),
) -> None:
    """Импорт файлового (легаси) реестра экспериментов в серверный режим —
    DOCKER.md §9. Идемпотентна: повторный запуск не дублирует уже
    импортированные (по имени) эксперименты."""
    from pathlib import Path

    from abkit.db.import_legacy import LegacyImportError, import_legacy_dir

    try:
        result = import_legacy_dir(Path(dir), owner)
    except LegacyImportError as e:
        console.print(f"[red]Ошибка:[/red] {e}")
        raise typer.Exit(code=1)

    if result.imported:
        console.print(f"[green]Импортировано ({len(result.imported)}):[/green] {', '.join(result.imported)}")
    if result.skipped_existing:
        console.print(
            f"[yellow]Уже были импортированы, пропущены ({len(result.skipped_existing)}):[/yellow] "
            f"{', '.join(result.skipped_existing)}"
        )
    if result.failed:
        console.print(f"[red]Ошибки ({len(result.failed)}):[/red]")
        for name, err in result.failed.items():
            console.print(f"  {name}: {err}")
    if not result.imported and not result.skipped_existing and not result.failed:
        console.print("Экспериментов для импорта не найдено (registry.json пуст?).")


if __name__ == "__main__":
    app()
