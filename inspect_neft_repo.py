# inspect_neft_repo.py
"""
Диагностика репозитория NEFT Processing.

Запускать ИЗ КОРНЯ репо:
    python inspect_neft_repo.py > neft_state.txt

Потом можно прислать мне содержимое neft_state.txt.
"""

import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent


def header(title: str):
    print("\n" + "=" * 80)
    print(f"= {title}")
    print("=" * 80)


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


def check_path(p: Path):
    return p.exists(), str(p.relative_to(ROOT))


def list_dir(p: Path, max_items=20):
    if not p.exists():
        print(f"[!] Каталог не найден: {p}")
        return
    items = sorted(p.iterdir())
    for item in items[:max_items]:
        kind = "DIR " if item.is_dir() else "FILE"
        print(f"- {kind:4} {item.name}")
    if len(items) > max_items:
        print(f"... и ещё {len(items) - max_items} элементов")


def section_basic():
    header("ОБЩАЯ ИНФОРМАЦИЯ")
    print(f"Текущее время: {datetime.now().isoformat()}")
    print(f"Корень репозитория: {ROOT}")
    print(f"Имя папки: {ROOT.name}")
    print()

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

    print("Проверка ключевых директорий:")
    for rel in expected_dirs:
        p = ROOT / rel
        exists = p.exists()
        mark = "OK " if exists else "NOK"
        print(f"[{mark}] {rel}")


def section_git():
    header("GIT-СОСТОЯНИЕ")

    rc, out, err = safe_run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    print(f"Текущая ветка: {out or 'не удалось определить'}")

    rc, out, err = safe_run(["git", "status", "--short"])
    if rc == 0:
        if not out:
            print("Статус: чистый (нет незакоммиченных изменений)")
        else:
            print("Незакоммиченные изменения:")
            print(out)
    else:
        print("Не удалось получить git status:", err)

    rc, out, err = safe_run(["git", "log", "-1", "--oneline"])
    if rc == 0:
        print("Последний коммит:")
        print(out)
    else:
        print("Не удалось получить последний коммит:", err)


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
        print(f"\n--- {name} ---")
        if not path.exists():
            print(f"[!] Каталог {path} не найден")
            continue

        dockerfile = path / "Dockerfile"
        pyproject = path / "pyproject.toml"
        req = path / "requirements.txt"
        app_dir = path / "app"

        print(f"[{'OK' if dockerfile.exists() else '!!'}] Dockerfile")
        print(f"[{'OK' if pyproject.exists() else '  '}] pyproject.toml")
        print(f"[{'OK' if req.exists() else '  '}] requirements.txt")
        print(f"[{'OK' if app_dir.exists() else '!!'}] app/")

        if app_dir.exists():
            mains = list(app_dir.glob("main.py"))
            if mains:
                print("main.py найден в app/:", ", ".join(str(m.relative_to(ROOT)) for m in mains))
            else:
                print("[!] main.py в app/ не найден")

            # Немного ключевых подпапок
            for sub in ["api", "schemas", "models", "services", "tests"]:
                sdir = app_dir / sub
                print(f"   [{'OK' if sdir.exists() else '  '}] app/{sub}")


def section_migrations():
    header("ALEMBIC-МИГРАЦИИ core-api")

    alembic_dir = ROOT / "services" / "core-api" / "app" / "alembic" / "versions"
    if not alembic_dir.exists():
        print("[!] Каталог миграций не найден:", alembic_dir)
        return

    versions = sorted(alembic_dir.glob("*.py"))
    print(f"Всего миграций: {len(versions)}")
    for v in versions:
        print("-", v.name)


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
        print(f"\n--- {name} ---")
        if not path.exists():
            print(f"[!] Каталог тестов не найден: {path}")
            continue
        tests = sorted(path.glob("test_*.py"))
        print(f"Количество файлов тестов: {len(tests)}")
        for t in tests:
            print("-", t.name)

    print("\n--- workers tasks ---")
    tasks_dir = workers_dir / "tasks"
    if tasks_dir.exists():
        files = sorted(tasks_dir.glob("*.py"))
        print(f"Файлы задач Celery ({len(files)}):")
        for f in files:
            print("-", f.name)
    else:
        print(f"[!] Каталог задач workers не найден: {tasks_dir}")


def section_endpoints():
    header("ENDPOINTS core-api (api/v1/endpoints)")

    endpoints_dir = ROOT / "services" / "core-api" / "app" / "api" / "v1" / "endpoints"
    if not endpoints_dir.exists():
        print("[!] Каталог endpoints не найден:", endpoints_dir)
        return

    list_dir(endpoints_dir, max_items=100)


def section_db_init():
    header("DB INIT СКРИПТЫ (db/init)")

    init_dir = ROOT / "db" / "init"
    if not init_dir.exists():
        print("[!] db/init не найден")
        return
    list_dir(init_dir, max_items=20)


def main():
    section_basic()
    section_git()
    section_services()
    section_migrations()
    section_tests()
    section_endpoints()
    section_db_init()

    print("\n\n[ДИАГНОСТИКА ЗАВЕРШЕНА]")


if __name__ == "__main__":
    main()
