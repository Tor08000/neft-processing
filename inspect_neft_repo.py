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
import json
import os
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPT_VERSION = "v0.3.0"
LOG_LINES: list[str] = []
RESULTS: dict[str, "CheckResult"] = {}

ALEMBIC_CONFIG_PATH = Path("platform/processing-core/app/alembic.ini")

SERVICES = {
    "core-api": {
        "service_dir": ROOT / "platform" / "processing-core",
        "app_dir": ROOT / "platform" / "processing-core" / "app",
        "tests_dir": ROOT / "platform" / "processing-core" / "app" / "tests",
        "alembic_versions": ROOT
        / "platform"
        / "processing-core"
        / "app"
        / "alembic"
        / "versions",
    },
    "auth-host": {
        "service_dir": ROOT / "platform" / "auth-host",
        "app_dir": ROOT / "platform" / "auth-host" / "app",
        "tests_dir": ROOT / "platform" / "auth-host" / "app" / "tests",
    },
    "ai-service": {
        "service_dir": ROOT / "platform" / "ai-services" / "risk-scorer",
        "app_dir": ROOT / "platform" / "ai-services" / "risk-scorer" / "app",
        "tests_dir": ROOT
        / "platform"
        / "ai-services"
        / "risk-scorer"
        / "app"
        / "tests",
    },
    "billing-clearing": {
        "service_dir": ROOT / "platform" / "billing-clearing",
        "app_dir": ROOT / "platform" / "billing-clearing" / "app",
        "tests_dir": ROOT / "platform" / "billing-clearing" / "app" / "tests",
        "tasks_dir": ROOT / "platform" / "billing-clearing" / "app" / "tasks",
    },
}

LEGACY_SERVICE_DIRS = [
    ROOT / "services" / "core-api",
    ROOT / "services" / "auth-host",
    ROOT / "services" / "ai-service",
    ROOT / "services" / "workers",
]


@dataclass
class CheckResult:
    status: str
    description: str | None = None
    is_env_issue: bool = False

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


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.strip().startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def section_env() -> CheckResult:
    header(".ENV ФАЙЛЫ")

    required_vars = {
        "NEFT_DEMO_ADMIN_EMAIL",
        "NEFT_DEMO_ADMIN_PASSWORD",
        "NEFT_DEMO_CLIENT_EMAIL",
        "NEFT_DEMO_CLIENT_PASSWORD",
    }

    files = {".env": ROOT / ".env", ".env.example": ROOT / ".env.example"}
    parsed: dict[str, dict[str, str]] = {}
    missing_files = []

    for name, path in files.items():
        if not path.exists():
            log(f"[WARN] {name} не найден (окружение разработчика)" )
            missing_files.append(name)
            continue
        log(f"[OK ] {name}")
        parsed[name] = parse_env_file(path)

    missing_required = {name: sorted(required_vars - set(values)) for name, values in parsed.items()}

    for name, missing in missing_required.items():
        if missing:
            log(
                f"[FAIL] В {name} отсутствуют ключевые переменные: {', '.join(missing)}"
            )

    if missing_files:
        log("[WARN] .env не сохранён в репозитории — проверьте локальные переменные")

    legacy_vars = {"ADMIN_EMAIL", "ADMIN_PASSWORD"}
    for name, values in parsed.items():
        legacy_present = sorted(legacy_vars & set(values))
        if legacy_present:
            log(
                f"[WARN] В {name} обнаружены legacy переменные: {', '.join(legacy_present)}"
            )

    if any(missing_required.values()):
        return CheckResult("FAIL", "Отсутствуют необходимые переменные .env")

    env_issue = bool(missing_files)
    status = "WARN" if env_issue else "OK"
    description = "Файл .env отсутствует" if env_issue else None
    return CheckResult(status, description, is_env_issue=env_issue)


def section_basic():
    header("ОБЩАЯ ИНФОРМАЦИЯ")
    log(f"Версия скрипта: inspect_neft_repo.py {SCRIPT_VERSION}")
    log(f"Текущее время: {datetime.now().isoformat()}")
    log(f"Корень репозитория: {ROOT}")
    log(f"Имя папки: {ROOT.name}")
    log()

    expected_dirs = [
        "platform/processing-core",
        "platform/auth-host",
        "platform/ai-services/risk-scorer",
        "platform/billing-clearing",
        "frontends/admin-ui",
        "frontends/client-portal",
        "services",  # env files and flower
        "services/flower",
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


def is_alembic_cli_issue(return_code: int, message: str) -> bool:
    lowered = message.lower()
    cp866_markers = [
        "¤«",
        "ўє«",
        "пў«пҐвбп",
        "ў­гваґ",
    ]
    return return_code == -1 or any(
        marker in lowered
        for marker in [
            "winerror 2",
            "no such file or directory",
            "не является внутренней или внешней командой",
            "is not recognized as an internal or external command",
            *cp866_markers,
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
            return CheckResult("SKIP", "Docker CLI недоступен или демон не запущен", True)

        log(f"[FAIL] docker compose завершился с ошибкой: {message}")
        return CheckResult("FAIL", message)

    declared_services = sorted(line.strip() for line in out.splitlines() if line.strip())
    log("Доступные сервисы docker compose:")
    for service in declared_services:
        log(f"- {service}")

    missing = [s for s in expected_services if s not in declared_services]

    if missing:
        log(f"[FAIL] Отсутствуют обязательные сервисы: {', '.join(missing)}")
        return CheckResult("FAIL", f"Отсутствуют сервисы: {', '.join(missing)}")

    log("[OK] Обязательные сервисы присутствуют")
    return CheckResult("OK")


def section_services():
    header("СЕРВИСЫ (platform и frontends)")

    platform_services = {
        "core-api": SERVICES["core-api"],
        "auth-host": SERVICES["auth-host"],
        "ai-service": SERVICES["ai-service"],
        "billing-clearing": SERVICES["billing-clearing"],
    }

    frontend_services = {
        "admin-web": ROOT / "frontends" / "admin-ui",
        "client-web": ROOT / "frontends" / "client-portal",
    }

    for name, path_info in platform_services.items():
        log(f"\n--- {name} ---")
        path = path_info["service_dir"]
        if not path.exists():
            log(f"[!] Каталог {path} не найден")
            continue

        dockerfile = path / "Dockerfile"
        pyproject = path / "pyproject.toml"
        req = path / "requirements.txt"

        log(f"[{'OK' if dockerfile.exists() else '!!'}] Dockerfile")
        log(f"[{'OK' if pyproject.exists() else '  '}] pyproject.toml")
        log(f"[{'OK' if req.exists() else '  '}] requirements.txt")

        app_dir = path_info.get("app_dir")
        if app_dir:
            log(f"[{'OK' if app_dir.exists() else '!!'}] app/")

            if app_dir.exists():
                mains = list(app_dir.glob("main.py"))
                if mains:
                    log(
                        "main.py найден в app/: "
                        + ", ".join(str(m.relative_to(ROOT)) for m in mains)
                    )
                else:
                    log("[!] main.py в app/ не найден")

                for sub in ["api", "schemas", "models", "services", "tests"]:
                    sdir = app_dir / sub
                    mark = "OK" if sdir.exists() else "  "
                    log(f"   [{mark}] app/{sub}")

    for name, path in frontend_services.items():
        log(f"\n--- {name} ---")
        if not path.exists():
            log(f"[!] Каталог {path} не найден")
            continue

        dockerfile = path / "Dockerfile"
        package_json = path / "package.json"
        log(f"[{'OK' if dockerfile.exists() else '!!'}] Dockerfile")
        log(f"[{'OK' if package_json.exists() else '  '}] package.json")
        src_dir = path / "src"
        log(f"[{'OK' if src_dir.exists() else '!!'}] src/")
        if src_dir.exists():
            main_entry = src_dir / "main.tsx"
            app_entry = src_dir / "App.tsx"
            log(f"[{'OK' if main_entry.exists() else '!!'}] src/main.tsx")
            log(f"[{'OK' if app_entry.exists() else '!!'}] src/App.tsx")

    legacy_missing = [path for path in LEGACY_SERVICE_DIRS if not path.exists()]
    if legacy_missing:
        log("\n[SKIP] legacy каталоги services/* отсутствуют — пропускаем проверки старой структуры")


def section_migrations() -> CheckResult:
    header("ALEMBIC-МИГРАЦИИ core-api")

    alembic_dir = SERVICES["core-api"]["alembic_versions"]
    if not alembic_dir.exists():
        log(f"[!] Каталог миграций не найден: {alembic_dir}")
        return CheckResult("FAIL", "Каталог миграций не найден")

    versions = sorted(alembic_dir.glob("*.py"))
    log(f"Всего миграций: {len(versions)}")
    for v in versions:
        log(f"- {v.name}")

    alembic_config = ROOT / ALEMBIC_CONFIG_PATH
    if not alembic_config.exists():
        log(
            "[FAIL] alembic config: Не найден конфиг Alembic по ожидаемому пути "
            f"{ALEMBIC_CONFIG_PATH}"
        )
        return CheckResult(
            "FAIL", f"Не найден конфиг Alembic по пути {ALEMBIC_CONFIG_PATH}"
        )

    rc, out, err = safe_run(
        ["alembic", "-c", str(alembic_config), "heads"],
        cwd=SERVICES["core-api"]["service_dir"],
    )
    message = err or out or "без подробностей"
    if rc != 0:
        if is_alembic_cli_issue(rc, message):
            log("[SKIP] alembic heads: Alembic CLI недоступен")
            return CheckResult(
                "SKIP",
                "Alembic CLI недоступен. Требуется установка или активация окружения.",
                True,
            )

        lowered = message.lower()
        if "no config file" in lowered:
            log(f"[FAIL] alembic heads: {message}")
            return CheckResult("FAIL", message)

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

    core_tests = SERVICES["core-api"]["tests_dir"]
    auth_tests = SERVICES["auth-host"]["tests_dir"]
    ai_tests = SERVICES["ai-service"]["tests_dir"]
    workers_dir = SERVICES["billing-clearing"]["app_dir"]

    for name, path in [
        ("core-api tests", core_tests),
        ("auth-host tests", auth_tests),
        ("ai-service tests", ai_tests),
        ("billing-clearing tests", SERVICES["billing-clearing"]["tests_dir"]),
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
    tasks_dir = SERVICES["billing-clearing"].get("tasks_dir")
    if tasks_dir.exists():
        files = sorted(tasks_dir.glob("*.py"))
        log(f"Файлы задач Celery ({len(files)}):")
        for f in files:
            log(f"- {f.name}")
    else:
        log(f"[!] Каталог задач workers не найден: {tasks_dir}")


def section_endpoints():
    header("ENDPOINTS core-api (app/api/routes)")

    endpoints_dir = SERVICES["core-api"]["app_dir"] / "api" / "routes"
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
        "auth": "http://localhost/admin/api/v1/auth/health",
        "core": "http://localhost/api/v1/health",
        "admin": "http://localhost/admin/",
        "client": "http://localhost/client/",
    }

    docker_result = RESULTS.get("docker compose")
    if docker_result and (
        docker_result.skip
        or (docker_result.fail and is_docker_env_issue(docker_result.description or ""))
    ):
        log(
            "[SKIP] health-checks: HTTP-проверки пропущены, т.к. Docker недоступен или стек не запущен."
        )
        return CheckResult(
            "SKIP", "Docker недоступен или стек не запущен", is_env_issue=True
        )

    results: dict[str, CheckResult] = {}

    for name, url in endpoints.items():
        log(f"\n--- {name} ---")
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                content = resp.read()
                status = getattr(resp, "status", None) or resp.getcode()
                content_type = resp.headers.get("Content-Type", "")
                log(f"URL: {url}")
                log(f"Статус: {status}")
                log(f"Длина ответа: {len(content)}")
                log(f"Content-Type: {content_type}")

            if status >= 400:
                results[name] = CheckResult(
                    "FAIL",
                    f"сервис {name} вернул код {status}",
                    name == "admin",
                )
                continue

            if name == "admin":
                if "application/json" in content_type.lower():
                    log("[FAIL] Ожидался HTML, получен JSON")
                    results[name] = CheckResult(
                        "FAIL", "admin-web вернул JSON вместо HTML", True
                    )
                    continue

                log("[OK] admin-web доступен (HTML)")
                results[name] = CheckResult("OK")
                continue

            if name == "client":
                if "application/json" in content_type.lower():
                    log("[FAIL] Ожидался HTML, получен JSON")
                    results[name] = CheckResult(
                        "FAIL", "client-web вернул JSON вместо HTML", True
                    )
                    continue

                log("[OK] client-web доступен (HTML)")
                results[name] = CheckResult("OK")
                continue

            try:
                data = json.loads(content)
            except Exception:  # noqa: BLE001
                log("[FAIL] Ответ не является JSON")
                results[name] = CheckResult(
                    "FAIL", f"сервис {name} вернул не-JSON ответ"
                )
                continue

            if isinstance(data, dict) and data.get("status") == "ok":
                log("[OK] Ответ health-check валиден")
                results[name] = CheckResult("OK")
            else:
                log("[FAIL] Неожиданный формат ответа health-check")
                results[name] = CheckResult(
                    "FAIL", f"сервис {name} вернул неожиданный ответ"
                )
        except urllib.error.HTTPError as e:
            log(f"[FAIL] HTTPError {e.code}: {e.reason}")
            results[name] = CheckResult(
                "FAIL", f"сервис {name} вернул код {e.code}"
            )
        except urllib.error.URLError as e:
            reason_text = str(e.reason)
            log(f"[FAIL] URLError: {reason_text}")
            if "connection refused" in reason_text.lower():
                results[name] = CheckResult(
                    "FAIL",
                    f"сервис {name} недоступен (connection refused)",
                    True,
                )
            else:
                results[name] = CheckResult(
                    "FAIL",
                    f"сервис {name} недоступен: {reason_text}",
                    True,
                )
        except Exception as e:  # noqa: BLE001
            log(f"[FAIL] Ошибка при запросе: {e}")
            results[name] = CheckResult(
                "FAIL", f"сервис {name} недоступен: {e}", True
            )

    if all(result.ok for result in results.values()):
        log("[OK] Все health-check запросы успешны")
        return CheckResult("OK")

    failed = [name for name, result in results.items() if not result.ok]
    env_issue = any(
        result.is_env_issue for name, result in results.items() if name in failed
    )
    log(f"[FAIL] Проблемы с сервисами: {', '.join(failed)}")
    return CheckResult("FAIL", f"Недоступны: {', '.join(failed)}", env_issue)


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
        return CheckResult("SKIP", "pytest пропущен по флагу", True)

    services = {
        "core-api": SERVICES["core-api"]["service_dir"],
        "auth-host": SERVICES["auth-host"]["service_dir"],
        "ai-service": SERVICES["ai-service"]["service_dir"],
        "billing-clearing": SERVICES["billing-clearing"]["service_dir"],
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

    repo_fail = any(
        result.fail and not result.is_env_issue for result in statuses.values()
    )
    env_only_issues = any(
        (result.fail and result.is_env_issue) or result.skip
        for result in statuses.values()
    )
    has_warn = any(result.warn for result in statuses.values())

    if repo_fail:
        summary = (
            "Есть проблемы в репозитории — требуется исправление конфигурации или кода"
        )
    elif env_only_issues:
        summary = "Репозиторий корректен, есть проблемы окружения"
    elif has_warn:
        summary = (
            "Репозиторий выглядит корректно, есть предупреждения (см. выше)."
        )
    else:
        summary = "Все проверки репозитория успешно пройдены"

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
    global RESULTS
    RESULTS = statuses

    section_basic()
    section_git()
    statuses[".env"] = section_env()
    statuses["docker compose"] = section_docker_compose(
        [
            "postgres",
            "redis",
            "admin-web",
            "client-web",
            "auth-host",
            "core-api",
            "ai-service",
            "workers",
            "beat",
            "flower",
            "gateway",
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
