from __future__ import annotations

import argparse
import asyncio
import sys

from app.seeds.demo_users import DemoUser, ensure_user, get_demo_users


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reset auth-host passwords.")
    parser.add_argument("--email", help="Email for the user to update.")
    parser.add_argument("--password", help="Password for the user to update.")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Reset demo users (admin/client/partner) using the fixed matrix.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force password reset even if it already matches.",
    )
    return parser.parse_args(argv)


async def _run_demo(force: bool) -> int:
    users = get_demo_users()
    for user in users:
        status = await ensure_user(user, force_password=force, sync_roles=True)
        print(f"{user.email}: {status}")
    return 0


async def _run_single(email: str, password: str, force: bool) -> int:
    user = DemoUser(email=email, password=password, full_name=None, roles=[])
    status = await ensure_user(user, force_password=force, sync_roles=False)
    print(f"{email}: {status}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    if args.demo:
        return asyncio.run(_run_demo(args.force))

    if not args.email or not args.password:
        print("error: provide --email and --password or use --demo", file=sys.stderr)
        return 2

    return asyncio.run(_run_single(args.email, args.password, args.force))


if __name__ == "__main__":
    raise SystemExit(main())
