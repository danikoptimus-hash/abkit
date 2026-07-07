# Развертывание abkit в Docker

Полноценный командный сервис: учетки, роли, Postgres, аудит-лог — поверх
той же библиотеки/Streamlit-приложения, что работает локально без Docker
(см. корневой [README.md](../README.md) для локального/файлового режима).
Техническая спецификация — [DOCKER.md](../DOCKER.md).

## Требования

- Docker Engine 24+ и Docker Compose v2 (`docker compose version`).
- Открытый порт (по умолчанию 8080) на хосте.

## Быстрый старт

```bash
git clone <repo> && cd abkit
cp .env.example .env
# отредактировать .env: как минимум ABKIT_SECRET_KEY и POSTGRES_PASSWORD
#   ABKIT_SECRET_KEY генерировать так: openssl rand -hex 32
docker compose up -d
docker compose exec app abkit-admin create-admin --email admin@co.com
# откройте http://<host>:8080, войдите под admin@co.com,
# заведите остальных пользователей во вкладке Admin
```

Через 1-2 минуты (сборка образа + старт Postgres) сервис доступен на
`http://<host>:8080`. Миграции БД (`alembic upgrade head`) применяются
автоматически при каждом старте контейнера `app` — накатывать их вручную не
нужно.

Если задать `ABKIT_ADMIN_EMAIL`/`ABKIT_ADMIN_PASSWORD` в `.env` (закомментированы
в `.env.example` по умолчанию) — первый администратор создастся автоматически
при первом старте, шаг `abkit-admin create-admin` можно пропустить.

## Управление пользователями

Все команды — через `docker compose exec app abkit-admin <command>`:

```bash
docker compose exec app abkit-admin create-admin --email admin@co.com [--name "Admin"] [--password ...]
docker compose exec app abkit-admin create-user  --email u@co.com --role editor
docker compose exec app abkit-admin reset-password --email u@co.com
docker compose exec app abkit-admin list-users
```

Если `--password` не передан — пароль генерируется и печатается в stdout один
раз (сохраните сразу, повторно его не показать). Пользователь получает флаг
`must_change_password` и обязан сменить пароль при первом входе (страница
«Профиль»/принудительная форма смены пароля).

То же самое можно сделать через веб-интерфейс — вкладка **Admin** (видна
только роли Admin): таблица пользователей, создание, смена роли,
блокировка/разблокировка, сброс пароля.

## Роли

| Право                                                          | Viewer | Editor | Admin |
|-----------------------------------------------------------------|:------:|:------:|:-----:|
| Смотреть эксперименты, отчеты, скачивать выборки                |   ✓    |   ✓    |   ✓   |
| Создавать эксперименты, запускать Analyze/Validation             |        |   ✓    |   ✓   |
| Менять статус/архивировать СВОИ эксперименты                     |        |   ✓    |   ✓   |
| Менять/архивировать ЧУЖИЕ эксперименты                            |        |        |   ✓   |
| Удалять эксперименты                                             |        |        |   ✓   |
| Управлять пользователями, смотреть общий аудит-лог                |        |        |   ✓   |

По умолчанию самостоятельная регистрация выключена (`ABKIT_ALLOW_SELF_REGISTRATION=false`)
— учетки заводит администратор, как в Apache Superset. Включение самостоятельной
регистрации выдает роль Viewer автоматически.

## Импорт данных из файлового (не-Docker) режима

Если вы уже пользовались `abkit` локально (файловый режим, без Docker) и
хотите перенести накопленные эксперименты на сервер:

```bash
# 1. Раскомментируйте в docker-compose.yml проброс volume для сервиса app:
#      - ./legacy_experiments:/import:ro
#    и положите туда старую папку экспериментов (ту, что указана как
#    experiments_dir/ABKIT_EXPERIMENTS_DIR в старой файловой установке —
#    там должны быть registry.json и папки экспериментов).
docker compose up -d --force-recreate app

# 2. Импортируйте, указав существующего пользователя-владельца:
docker compose exec app abkit-admin import-legacy --dir /import --owner admin@co.com
```

Команда идемпотентна: повторный запуск не создаст дублей — уже
импортированные (по имени) эксперименты просто пропускаются, с чёткой
пометкой в выводе. Импортируются конфиг, назначения групп (assignments),
HTML-отчеты и results.json, если они есть; статус и исторические даты
(created_at/started_at/completed_at) сохраняются как в исходной установке.

## Обновление версии

```bash
git pull
docker compose build
docker compose up -d
```

Миграции БД применяются автоматически при старте `app` — ручных действий не
требуется. Даунтайм — время пересборки образа + перезапуска контейнера `app`
(Postgres не перезапускается, если его образ/конфиг не менялись).

## Бэкап и восстановление

Бэкап (структурные данные + бинарные артефакты — DOCKER.md §5):

```bash
docker compose exec postgres pg_dump -U "${POSTGRES_USER:-abkit}" "${POSTGRES_DB:-abkit}" > backup.sql
docker run --rm -v abkit_abkit_data:/data -v "$(pwd)":/backup alpine \
    tar -czf /backup/data.tgz -C /data .
```

Восстановление (на новом/пустом окружении):

```bash
docker compose up -d postgres
cat backup.sql | docker compose exec -T postgres psql -U "${POSTGRES_USER:-abkit}" "${POSTGRES_DB:-abkit}"
docker run --rm -v abkit_abkit_data:/data -v "$(pwd)":/backup alpine \
    sh -c "cd /data && tar -xzf /backup/data.tgz"
docker compose up -d
```

`docker compose down` (без `-v`) НЕ удаляет volumes — данные переживают
остановку/пересоздание контейнеров. `docker compose down -v` volumes удаляет
безвозвратно — используйте только осознанно (например, чтобы начать с чистого
листа локально).

## Логи

```bash
docker compose logs -f app        # структурированные JSON-логи (ABKIT_LOG_FORMAT=json по умолчанию)
docker compose logs -f postgres
docker compose logs -f nginx
```

`ABKIT_LOG_FORMAT=text` в `.env` — человекочитаемый формат вместо JSON, для
отладки на живую руку. `ABKIT_LOG_LEVEL` — стандартные уровни Python-логирования
(`DEBUG`/`INFO`/`WARNING`/`ERROR`).

## Смена порта

Отредактируйте `ABKIT_PORT` в `.env` (по умолчанию 8080) и перезапустите
`nginx`:

```bash
docker compose up -d nginx
```

## TLS (опционально)

По умолчанию сервис работает по HTTP. Чтобы включить HTTPS: положите
сертификаты в `docker/certs/` (`fullchain.pem`/`privkey.pem`), раскомментируйте
проброс `./docker/certs:/etc/nginx/certs:ro` в `docker-compose.yml` (сервис
`nginx`) и блок `listen 443 ssl; ssl_certificate ...` в
`docker/nginx.conf.template`.

## Безопасность

Чек-лист — DOCKER.md §11 (пароли только argon2id-хеши, cookie SameSite=Lax,
Postgres не публикуется наружу, секреты не логируются, `.env` в `.gitignore`,
контейнер `app` работает от не-root пользователя). `ABKIT_SECRET_KEY` и
`POSTGRES_PASSWORD` в `.env` — обязательно смените дефолтные значения перед
продакшн-развертыванием; приложение откажется стартовать, если
`ABKIT_SECRET_KEY` не задан или похож на дефолтный `change-me...`.
