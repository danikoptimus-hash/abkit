"""users.folders_panel_collapsed: первая per-user UI-настройка

Панель папок на /experiments до сих пор жила в локальном useState и сбрасывалась
при каждом монтировании. Требование пакета share+folders: по умолчанию —
свернута, но осознанный выбор пользователя (развернул/свернул) должен
переживать навигацию и перезагрузку.

Почему серверная колонка, а не localStorage: своего механизма пользовательских
настроек в приложении не было вовсе (это первая), а localStorage привязан к
браузеру, не к пользователю — на втором устройстве настройка бы не поехала, и
при этом появился бы ПЕРВЫЙ клиентский стор состояния в проекте, где всё
остальное состояние живет на сервере. Настройка едет в UserOut вместе с
остальным про текущего пользователя, поэтому лишнего запроса на старте нет.

Почему типизированная BOOLEAN-колонка, а не JSONB `preferences`: у `users` весь
остальной "флаговый" ряд — именно такие колонки (is_active,
must_change_password), они греппаются и типизированы от БД до TS. JSONB тут был
бы первым бесschema-состоянием в проекте ради одного булева. Настройка №2 —
такая же аддитивная миграция (правило (б)); если их приедет сразу несколько,
тогда и стоит пересмотреть в пользу JSONB.

server_default=true — это и есть продуктовое решение "свернута по умолчанию":
существующие пользователи после миграции получают свернутую панель, ровно как
новые. Отдельного "никогда не выбирал" состояния не нужно: свернуто по
умолчанию, разложил — запомнили.

Revision ID: 0018
Revises: 0017
Create Date: 2026-07-17
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "folders_panel_collapsed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "folders_panel_collapsed")
