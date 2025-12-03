# inspect_neft_repo.py
"""
Диагностика репозитория NEFT Processing.

Запускать ИЗ КОРНЯ репо:
    python inspect_neft_repo.py

Опции:
    --run-tests   запуск pytest для core-api, auth-host и ai-service
    --output PATH путь до файла отчёта (по умолчанию docs/diag/neft_state_YYYYMMDD_HHMM.txt)

Отчёт печатается в консоль и сохраняется в docs/diag/.
"""

import argparse
import os
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPT_VERSION = "v0.1.5"
LOG_LINES: list[str] = []


@dataclass
class CheckResult:
    status: str
    description: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == "OK"

    @property
    def warn(self) -> bool:
        return self.status == "WARN"

    @property
    def fail(self) -> bool:
        return self.status == "FAIL"

    @property
    def skip(self) -> bool:
        return self.status == "SKIP"


def log(message: str = ""):
    print(message)
    LOG_LINES.append(message)


def header(title: str):
    log("\n" + "=" * 80)
    log(f"= {title}")
    log("=" * 80)


def safe_run(cmd, cwd=None):
    try:
        res = subprocess.run(
            cmd,
            cwd=cwd or ROOT,
            capture_output=True,
            text=True,
            shell=os.name == "nt",
        )
        out = (res.stdout or "").strip()
        err = (res.stderr or "").strip()
        return res.returncode, out, err
    except Exception as e:
        return -1, "", f"EXCEPTION: {e}"


def list_dir(p: Path, max_items=20):
    if not p.exists():
        log(f"[!] Каталог не найден: {p}")
        return
    items = sorted(p.iterdir())
    for item in items[:max_items]:
        kind = "DIR " if item.is_dir() else "FILE"
        log(f"- {kind:4} {item.name}")
    if len(items) > max_items:
        log(f"... и ещё {len(items) - max_items} элементов")


def section_basic():
    header("ОБЩАЯ ИНФОРМАЦИЯ")
    log(f"Версия скрипта: inspect_neft_repo.py {SCRIPT_VERSION}")
    log(f"Текущее время: {datetime.now().isoformat()}")
    log(f"Корень репозитория: {ROOT}")
    log(f"Имя папки: {ROOT.name}")
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
        p = ROOT / rel
        exists = p.exists()
        mark = "OK " if exists else "NOK"
        log(f"[{mark}] {rel}")


def section_git():
    header("GIT-СОСТОЯНИЕ")

    rc, out, err = safe_run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    log(f"Текущая ветка: {out or 'не удалось определить'}")

    rc, out, err = safe_run(["git", "status", "--short"])
    if rc == 0:
        if not out:
            log("Статус: чистый (нет незакоммиченных изменений)")
        else:
            log("Незакоммиченные изменения:")
            log(out)
    else:
        log(f"Не удалось получить git status: {err}")

    rc, out, err = safe_run(["git", "log", "-1", "--oneline"])
    if rc == 0:
        log("Последний коммит:")
        log(out)
    else:
        log(f"Не удалось получить последний коммит: {err}")


def is_docker_env_issue(error_message: str) -> bool:
    lowered = error_message.lower()
    return any(
        marker in lowered
        for marker in [
            "winerror 2",
            "no such file or directory",
            "not recognized as an internal or external command",
            "cannot connect to the docker daemon",
            "error during connect",
            "daemon is not running",
        ]
    )


def section_docker_compose(expected_services: list[str]) -> CheckResult:
    header("DOCKER COMPOSE")

    rc, out, err = safe_run(["docker", "compose", "config", "--services"])
    if rc != 0:
        message = err or out or "docker compose недоступен"
        if is_docker_env_issue(message) or rc == -1:
            log("[SKIP] docker compose недоступен: Docker CLI недоступен или демон не запущен.")
            log("       Проверьте установку Docker Desktop и запустите Docker перед диагностикой.")
            return CheckResult("SKIP", "Docker CLI недоступен или демон не запущен")

        log(f"[FAIL] docker compose завершился с ошибкой: {message}")
        return CheckResult("FAIL", message)

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
        return CheckResult("OK")

    return CheckResult("WARN", "Список сервисов отличается от ожиданий")


def section_services():
    header("СЕРВИСЫ (core-api, auth-host, workers, ai-service, admin-web)")

    services = {
        "core-api": ROOT / "services" / "core-api",
        "auth-host": ROOT / "services" / "auth-host",
        "workers": ROOT / "services" / "workers",
        "ai-service": ROOT / "services" / "ai-service",
        "admin-web": ROOT / "services" / "admin-web",
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

        log(f"[{'OK' if dockerfile.exists() else '!!'}] Dockerfile")
        log(f"[{'OK' if pyproject.exists() else '  '}] pyproject.toml")
        log(f"[{'OK' if req.exists() else '  '}] requirements.txt")
        log(f"[{'OK' if app_dir.exists() else '!!'}] app/")

        if app_dir.exists():
            mains = list(app_dir.glob("main.py"))
            if mains:
                log("main.py найден в app/: " + ", ".join(str(m.relative_to(ROOT)) for m in mains))
            else:
                log("[!] main.py в app/ не найден")

            # Немного ключевых подпапок
            for sub in ["api", "schemas", "models", "services", "tests"]:
                sdir = app_dir / sub
                log(f"   [{'OK' if sdir.exists() else '  '}] app/{sub}")


def section_migrations() -> CheckResult:
    header("ALEMBIC-МИГРАЦИИ core-api")

    alembic_dir = ROOT / "services" / "core-api" / "app" / "alembic" / "versions"
    if not alembic_dir.exists():
        log(f"[!] Каталог миграций не найден: {alembic_dir}")
        return CheckResult("FAIL", "Каталог миграций не найден")

    versions = sorted(alembic_dir.glob("*.py"))
    log(f"Всего миграций: {len(versions)}")
    for v in versions:
        log(f"- {v.name}")

    rc, out, err = safe_run(["alembic", "heads"], cwd=ROOT / "services" / "core-api")
    message = err or out or "без подробностей"
    if rc != 0:
        lowered = message.lower()
        if rc == -1 or "winerror 2" in lowered or "no such file or directory" in lowered:
            log("[SKIP] alembic heads: Alembic CLI недоступен. Активируйте виртуальное окружение или установите Alembic.")
            return CheckResult("SKIP", "Alembic CLI недоступен")

        log(f"[FAIL] Не удалось выполнить 'alembic heads': {message}")
        return CheckResult("FAIL", message)

    heads = [line for line in out.splitlines() if line.strip()]
    log("Вывод 'alembic heads':")
    for line in heads:
        log(line)

    if len(heads) == 1:
        log("[OK] Найден один head Alembic")
        return CheckResult("OK")

    log(f"[FAIL] Количество head: {len(heads)}")
    return CheckResult("FAIL", f"Найдено head: {len(heads)}")


def section_tests():
    header("ТЕСТЫ")

    core_tests = ROOT / "services" / "core-api" / "app" / "tests"
    auth_tests = ROOT / "services" / "auth-host" / "app" / "tests"
    ai_tests = ROOT / "services" / "ai-service" / "app" / "tests"
    workers_dir = ROOT / "services" / "workers" / "app"

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


def section_endpoints():
    header("ENDPOINTS core-api (api/v1/endpoints)")

    endpoints_dir = ROOT / "services" / "core-api" / "app" / "api" / "v1" / "endpoints"
    if not endpoints_dir.exists():
        log(f"[!] Каталог endpoints не найден: {endpoints_dir}")
        return

    list_dir(endpoints_dir, max_items=100)


def section_db_init():
    header("DB INIT СКРИПТЫ (db/init)")

    init_dir = ROOT / "db" / "init"
    if not init_dir.exists():
        log("[!] db/init не найден")
        return
    list_dir(init_dir, max_items=20)


def section_health_checks() -> CheckResult:
    header("HEALTH-CHECK СЕРВИСОВ")

    endpoints = {
        "auth": "http://localhost/api/auth/api/v1/health",
        "core": "http://localhost/api/core/api/v1/health",
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
        except urllib.error.HTTPError as e:
            log(f"[FAIL] HTTPError {e.code}: {e.reason}")
            results[name] = False
        except urllib.error.URLError as e:
            log(f"[FAIL] URLError: {e.reason}")
            results[name] = False
        except Exception as e:  # noqa: BLE001
            log(f"[FAIL] Ошибка при запросе: {e}")
            results[name] = False

    overall = all(results.values()) if results else False
    if overall:
        log("[OK] Все health-check запросы успешны")
        return CheckResult("OK")

    failed = [name for name, ok in results.items() if not ok]
    log(f"[FAIL] Проблемы с сервисами: {', '.join(failed)}")
    return CheckResult("FAIL", f"Недоступны: {', '.join(failed)}")


def run_pytest_for_service(name: str, path: Path):
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


def section_run_tests(run_tests: bool) -> CheckResult:
    header("ЗАПУСК ТЕСТОВ")

    if not run_tests:
        log("Флаг --run-tests не передан, пропускаем запуск pytest")
        return CheckResult("SKIP", "pytest пропущен по флагу")

    services = {
        "core-api": ROOT / "services" / "core-api",
        "auth-host": ROOT / "services" / "auth-host",
        "ai-service": ROOT / "services" / "ai-service",
    }

    results = {name: run_pytest_for_service(name, path) for name, path in services.items()}

    passed = [name for name, ok in results.items() if ok]
    failed = [name for name, ok in results.items() if not ok]
    log("\nСводка pytest:")
    log(f"Passed: {', '.join(passed) if passed else 'нет'}")
    log(f"Failed: {', '.join(failed) if failed else 'нет'}")

    overall = all(results.values()) if results else False
    return CheckResult("OK" if overall else "FAIL", "pytest запускался" if run_tests else None)


def write_output(output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    log(f"\n[СОХРАНЕНО] Отчёт будет записан в {output_path}")
    output_path.write_text("\n".join(LOG_LINES), encoding="utf-8")


def summarize_status(statuses: dict[str, CheckResult]):
    header("ИТОГОВЫЙ ОТЧЁТ")
    for key, result in statuses.items():
        suffix = f": {result.description}" if result.description else ""
        log(f"[{result.status}] {key}{suffix}")

    has_fail = any(result.fail for result in statuses.values())
    has_warn = any(result.warn for result in statuses.values())
    has_skip = any(result.skip for result in statuses.values())

    if has_fail:
        summary = "Есть проблемы в репозитории — требуется исправление конфигурации или кода"
    elif has_warn:
        summary = "Проверки завершены с предупреждениями"
    elif has_skip:
        summary = "Проверки репозитория пройдены, есть пропуски из-за окружения"
    else:
        summary = "Все проверки OK"

    log(f"\n[ИТОГ] {summary}")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Диагностика репозитория NEFT Processing")
    parser.add_argument("--run-tests", action="store_true", help="Запустить pytest для основных сервисов")
    parser.add_argument(
        "--output",
        type=Path,
        help="Путь к файлу отчёта. По умолчанию docs/diag/neft_state_YYYYMMDD_HHMM.txt",
    )
    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    default_output = ROOT / "docs" / "diag" / f"neft_state_{timestamp}.txt"
    output_path = args.output or default_output

    log(f"Отчёт будет сохранён в: {output_path}")

    statuses: dict[str, CheckResult] = {}

    section_basic()
    section_git()
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
            "otel-collector",
            "jaeger",
            "prometheus",
            "grafana",
        ]
    )
    section_services()
    statuses["alembic heads"] = section_migrations()
    section_tests()
    statuses["health-checks"] = section_health_checks()
    statuses["pytest"] = section_run_tests(args.run_tests)
    section_endpoints()
    section_db_init()
    summarize_status(statuses)

    write_output(output_path)

    log("\n\n[ДИАГНОСТИКА ЗАВЕРШЕНА]")


if __name__ == "__main__":
    main()
