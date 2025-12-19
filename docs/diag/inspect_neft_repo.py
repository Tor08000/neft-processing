#!/usr/bin/env python3
"""
Расширенная диагностика репозитория NEFT Processing.

Запускать из корня репозитория или напрямую из каталога docs/diag/:
    python docs/diag/inspect_neft_repo.py [--run-tests] [--skip-health] [--output PATH]

Опции:
    --run-tests     запуск pytest для core-api, auth-host и ai-service
    --skip-health   пропустить HTTP health-check запросы (если окружение не поднято)
    --output PATH   путь до файла отчёта (по умолчанию docs/diag/neft_state_YYYYMMDD_HHMM.txt)

Отчёт печатается в консоль и сохраняется в docs/diag/.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Iterable


# ------------------------------- инфраструктура вывода -------------------------------
LOG_LINES: list[str] = []


def log(message: str = "") -> None:
    print(message)
    LOG_LINES.append(message)


def header(title: str) -> None:
    separator = "=" * 80
    log(f"\n{separator}")
    log(f"= {title}")
    log(separator)


# ------------------------------- утилиты --------------------------------------------

def detect_repo_root(start: Path) -> Path:
    for parent in [start] + list(start.parents):
        if (parent / ".git").exists():
            return parent
    return start


def safe_run(cmd: Iterable[str] | str, cwd: Path | None = None):
    try:
        res = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            shell=isinstance(cmd, str),
        )
        out = (res.stdout or "").strip()
        err = (res.stderr or "").strip()
        return res.returncode, out, err
    except Exception as exc:  # noqa: BLE001
        return -1, "", f"EXCEPTION: {exc}"


def list_dir(p: Path, max_items: int = 20) -> None:
    if not p.exists():
        log(f"[!] Каталог не найден: {p}")
        return
    items = sorted(p.iterdir())
    for item in items[:max_items]:
        kind = "DIR " if item.is_dir() else "FILE"
        log(f"- {kind:4} {item.name}")
    if len(items) > max_items:
        log(f"... и ещё {len(items) - max_items} элементов")


REPO_ROOT = detect_repo_root(Path(__file__).resolve().parents[2])
DOCS_ROOT = REPO_ROOT / "docs" / "diag"


# ------------------------------- проверки ------------------------------------------

def section_basic() -> None:
    header("ОБЩАЯ ИНФОРМАЦИЯ")
    log(f"Текущее время: {datetime.now().isoformat()}")
    log(f"Корень репозитория: {REPO_ROOT}")
    log(f"Текущий файл диагностики: {Path(__file__).resolve()}")
    log()

    expected_dirs = [
        "services",
        "services/core-api",
        "services/auth-host",
        "services/admin-web",
        "services/ai-service",
        "services/workers",
        "shared/python/neft_shared",
        "db",
        "nginx",
        "infra/k8s",
        "infra/terraform",
        "docs",
    ]

    log("Проверка ключевых директорий:")
    for rel in expected_dirs:
        p = REPO_ROOT / rel
        exists = p.exists()
        mark = "OK " if exists else "NOK"
        log(f"[{mark}] {rel}")


def section_git() -> None:
    header("GIT-СОСТОЯНИЕ")

    rc, out, err = safe_run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=REPO_ROOT)
    log(f"Текущая ветка: {out or 'не удалось определить'}")

    rc, out, err = safe_run(["git", "status", "--short"], cwd=REPO_ROOT)
    if rc == 0:
        if not out:
            log("Статус: чистый (нет незакоммиченных изменений)")
        else:
            log("Незакоммиченные изменения:")
            log(out)
    else:
        log(f"Не удалось получить git status: {err}")

    rc, out, err = safe_run(["git", "log", "-1", "--oneline"], cwd=REPO_ROOT)
    if rc == 0:
        log("Последний коммит:")
        log(out)
    else:
        log(f"Не удалось получить последний коммит: {err}")


def section_env() -> None:
    header(".ENV ФАЙЛЫ")
    env_path = REPO_ROOT / ".env"
    example_path = REPO_ROOT / ".env.example"

    for path in [env_path, example_path]:
        mark = "OK " if path.exists() else "NOK"
        log(f"[{mark}] {path.relative_to(REPO_ROOT)}")

    required_vars = ["ADMIN_EMAIL", "ADMIN_PASSWORD"]
    if env_path.exists():
        content = env_path.read_text(encoding="utf-8", errors="ignore")
        for var in required_vars:
            present = f"{var}=" in content
            log(f"[{ 'OK ' if present else 'NOK' }] {var} в .env")
    else:
        log("[WARN] .env отсутствует, переменные проверить невозможно")


def section_docker_compose(expected_services: list[str]) -> bool:
    header("DOCKER COMPOSE")

    compose_file = REPO_ROOT / "docker-compose.yml"
    log(f"Файл docker-compose.yml: {'OK' if compose_file.exists() else 'NOK'}")

    rc, out, err = safe_run(["docker", "compose", "config", "--services"], cwd=REPO_ROOT)
    if rc != 0:
        log(f"[FAIL] docker compose недоступен: {err or 'неизвестная ошибка'}")
        return False

    declared_services = sorted(line.strip() for line in out.splitlines() if line.strip())
    log("Доступные сервисы docker compose:")
    for service in declared_services:
        log(f"- {service}")

    missing = [s for s in expected_services if s not in declared_services]
    extra = [s for s in declared_services if s not in expected_services]

    if missing:
        log(f"[WARN] Отсутствуют ожидаемые сервисы: {', '.join(missing)}")
    if extra:
        log(f"[WARN] Обнаружены неожиданные сервисы: {', '.join(extra)}")

    if not missing and not extra:
        log("[OK] Список сервисов соответствует ожиданиям")
        return True

    return False


def section_services() -> None:
    header("СЕРВИСЫ (core-api, auth-host, workers, ai-service, admin-web)")

    services = {
        "core-api": REPO_ROOT / "services" / "core-api",
        "auth-host": REPO_ROOT / "services" / "auth-host",
        "workers": REPO_ROOT / "services" / "workers",
        "ai-service": REPO_ROOT / "services" / "ai-service",
        "admin-web": REPO_ROOT / "services" / "admin-web",
    }

    for name, path in services.items():
        log(f"\n--- {name} ---")
        if not path.exists():
            log(f"[!] Каталог {path} не найден")
            continue

        dockerfile = path / "Dockerfile"
        pyproject = path / "pyproject.toml"
        req = path / "requirements.txt"
        app_dir = path / "app"

        log(f"[{ 'OK' if dockerfile.exists() else '!!'}] Dockerfile")
        log(f"[{ 'OK' if pyproject.exists() else '  '}] pyproject.toml")
        log(f"[{ 'OK' if req.exists() else '  '}] requirements.txt")
        log(f"[{ 'OK' if app_dir.exists() else '!!'}] app/")

        if app_dir.exists():
            mains = list(app_dir.glob("main.py"))
            if mains:
                rels = ", ".join(str(m.relative_to(REPO_ROOT)) for m in mains)
                log("main.py найден в app/: " + rels)
            else:
                log("[!] main.py в app/ не найден")

            for sub in ["api", "schemas", "models", "services", "tests"]:
                sdir = app_dir / sub
                log(f"   [{ 'OK' if sdir.exists() else '  '}] app/{sub}")


def section_migrations() -> bool:
    header("ALEMBIC-МИГРАЦИИ core-api")

    alembic_dir = REPO_ROOT / "services" / "core-api" / "app" / "alembic" / "versions"
    if not alembic_dir.exists():
        log(f"[!] Каталог миграций не найден: {alembic_dir}")
        return False

    versions = sorted(alembic_dir.glob("*.py"))
    log(f"Всего миграций: {len(versions)}")
    for v in versions:
        log(f"- {v.name}")

    rc, out, err = safe_run(["alembic", "heads"], cwd=REPO_ROOT / "services" / "core-api")
    if rc != 0:
        log(f"[FAIL] Не удалось выполнить 'alembic heads': {err or 'без подробностей'}")
        return False

    heads = [line for line in out.splitlines() if line.strip()]
    log("Вывод 'alembic heads':")
    for line in heads:
        log(line)

    if len(heads) == 1:
        log("[OK] Найден один head Alembic")
        return True

    log(f"[FAIL] Количество head: {len(heads)}")
    return False


def section_tests() -> None:
    header("ТЕСТЫ")

    core_tests = REPO_ROOT / "services" / "core-api" / "app" / "tests"
    auth_tests = REPO_ROOT / "services" / "auth-host" / "app" / "tests"
    ai_tests = REPO_ROOT / "services" / "ai-service" / "app" / "tests"
    workers_dir = REPO_ROOT / "services" / "workers" / "app"

    for name, path in [
        ("core-api tests", core_tests),
        ("auth-host tests", auth_tests),
        ("ai-service tests", ai_tests),
    ]:
        log(f"\n--- {name} ---")
        if not path.exists():
            log(f"[!] Каталог тестов не найден: {path}")
            continue
        tests = sorted(path.glob("test_*.py"))
        log(f"Количество файлов тестов: {len(tests)}")
        for t in tests:
            log(f"- {t.name}")

    log("\n--- workers tasks ---")
    tasks_dir = workers_dir / "tasks"
    if tasks_dir.exists():
        files = sorted(tasks_dir.glob("*.py"))
        log(f"Файлы задач Celery ({len(files)}):")
        for f in files:
            log(f"- {f.name}")
    else:
        log(f"[!] Каталог задач workers не найден: {tasks_dir}")


def section_endpoints() -> None:
    header("ENDPOINTS core-api (api/v1/endpoints)")

    endpoints_dir = REPO_ROOT / "services" / "core-api" / "app" / "api" / "v1" / "endpoints"
    if not endpoints_dir.exists():
        log(f"[!] Каталог endpoints не найден: {endpoints_dir}")
        return

    list_dir(endpoints_dir, max_items=100)


def section_db_init() -> None:
    header("DB INIT СКРИПТЫ (db/init)")

    init_dir = REPO_ROOT / "db" / "init"
    if not init_dir.exists():
        log("[!] db/init не найден")
        return
    list_dir(init_dir, max_items=20)


def section_health_checks(skip_health: bool) -> bool | None:
    header("HEALTH-CHECK СЕРВИСОВ")

    if skip_health:
        log("Флаг --skip-health активирован, HTTP проверки пропущены")
        return None

    endpoints = {
        "auth": "http://localhost/admin/api/v1/auth/health",
        "core": "http://localhost/api/v1/health",
        "admin": "http://localhost/admin/",
    }

    results: dict[str, bool] = {}

    for name, url in endpoints.items():
        log(f"\n--- {name} ---")
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                content = resp.read()
                status = getattr(resp, "status", None) or resp.getcode()
                log(f"URL: {url}")
                log(f"Статус: {status}")
                log(f"Длина ответа: {len(content)}")
                results[name] = status == 200
        except urllib.error.HTTPError as exc:
            log(f"[FAIL] HTTPError {exc.code}: {exc.reason}")
            results[name] = False
        except urllib.error.URLError as exc:
            log(f"[FAIL] URLError: {exc.reason}")
            results[name] = False
        except Exception as exc:  # noqa: BLE001
            log(f"[FAIL] Ошибка при запросе: {exc}")
            results[name] = False

    overall = all(results.values()) if results else False
    if overall:
        log("[OK] Все health-check запросы успешны")
    else:
        failed = [name for name, ok in results.items() if not ok]
        log(f"[FAIL] Проблемы с сервисами: {', '.join(failed)}")
    return overall


def run_pytest_for_service(name: str, path: Path) -> bool:
    log(f"\n--- pytest {name} ---")
    if not path.exists():
        log(f"[FAIL] Каталог сервиса не найден: {path}")
        return False

    rc, out, err = safe_run(["pytest"], cwd=path)
    if rc == 0:
        log("[OK] pytest passed")
    else:
        log("[FAIL] pytest завершился с ошибкой")
    if out:
        log(out)
    if err:
        log(err)
    return rc == 0


def section_run_tests(run_tests: bool) -> bool | None:
    header("ЗАПУСК ТЕСТОВ")

    if not run_tests:
        log("Флаг --run-tests не передан, пропускаем запуск pytest")
        return None

    services = {
        "core-api": REPO_ROOT / "services" / "core-api",
        "auth-host": REPO_ROOT / "services" / "auth-host",
        "ai-service": REPO_ROOT / "services" / "ai-service",
    }

    results = {name: run_pytest_for_service(name, path) for name, path in services.items()}

    passed = [name for name, ok in results.items() if ok]
    failed = [name for name, ok in results.items() if not ok]
    log("\nСводка pytest:")
    log(f"Passed: {', '.join(passed) if passed else 'нет'}")
    log(f"Failed: {', '.join(failed) if failed else 'нет'}")

    return all(results.values()) if results else False


def write_output(output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    log(f"\n[СОХРАНЕНО] Отчёт будет записан в {output_path}")
    output_path.write_text("\n".join(LOG_LINES), encoding="utf-8")


def summarize_status(statuses: dict[str, bool | None]) -> bool:
    header("ИТОГОВЫЙ ОТЧЁТ")
    for key, value in statuses.items():
        if value is True:
            mark = "OK"
        elif value is False:
            mark = "FAIL"
        else:
            mark = "SKIP"
        log(f"[{mark}] {key}")

    overall_ok = all(value for value in statuses.values() if value is not None)
    if overall_ok:
        log("\n[ИТОГ] Все проверки OK")
    else:
        log("\n[ИТОГ] Есть проблемы в проверках")
    return overall_ok


def main() -> None:
    parser = argparse.ArgumentParser(description="Диагностика репозитория NEFT Processing")
    parser.add_argument("--run-tests", action="store_true", help="Запустить pytest для основных сервисов")
    parser.add_argument("--skip-health", action="store_true", help="Пропустить HTTP health-check запросы")
    parser.add_argument(
        "--output",
        type=Path,
        help="Путь к файлу отчёта. По умолчанию docs/diag/neft_state_YYYYMMDD_HHMM.txt",
    )
    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    default_output = DOCS_ROOT / f"neft_state_{timestamp}.txt"
    output_path = args.output or default_output

    log(f"Отчёт будет сохранён в: {output_path}")

    statuses: dict[str, bool | None] = {}

    section_basic()
    section_git()
    section_env()
    statuses["docker compose"] = section_docker_compose(
        [
            "postgres",
            "redis",
            "admin-web",
            "auth-host",
            "core-api",
            "ai-service",
            "workers",
            "beat",
            "flower",
            "gateway",
            "postgres-data",
        ]
    )
    section_services()
    statuses["alembic heads"] = section_migrations()
    section_tests()
    statuses["health-checks"] = section_health_checks(args.skip_health)
    statuses["pytest"] = section_run_tests(args.run_tests)
    section_endpoints()
    section_db_init()
    summarize_status(statuses)

    write_output(output_path)

    log("\n\n[ДИАГНОСТИКА ЗАВЕРШЕНА]")


if __name__ == "__main__":
    main()
