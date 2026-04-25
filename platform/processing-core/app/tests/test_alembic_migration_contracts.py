from __future__ import annotations

import ast
from pathlib import Path

import pytest


MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "alembic" / "versions"

HELPER_NAMES = {"index_exists", "constraint_exists", "column_exists"}
FORBIDDEN_DEFINITIONS = HELPER_NAMES | {"_index_exists"}
ALLOWED_KEYWORDS = {
    "index_exists": {"schema"},
    "constraint_exists": {"schema"},
    "column_exists": {"schema"},
}
MIN_POSITIONAL = {"index_exists": 2, "constraint_exists": 3, "column_exists": 3}
MAX_POSITIONAL = {"index_exists": 3, "constraint_exists": 4, "column_exists": 4}
LEGACY_UNGUARDED_MIGRATIONS = {
    "20291325_0062_logistics_core_v1.py",
    "20291330_0063_logistics_core_v2.py",
    "20291401_0065_crm_core_v1.py",
    "20291405_0066_crm_subscriptions_v1.py",
    "20291410_0067_subscription_billing_job_type.py",
    "20291420_0071_subscriptions_v2_segments_and_rules.py",
    "20291510_0070_money_flow_v2.py",
    "20291520_0074_logistics_navigator_core.py",
    "20291560_0078_ops_reason_codes.py",
    "20291570_0079_fleet_intelligence_v1.py",
    "20291580_0080_fleet_intelligence_trends_v2.py",
    "20291590_0081_fleet_control_v3.py",
    "20297120_0117_create_core_base_tables_v1.py",
    "20297155_0123_ensure_core_operations_table.py",
    "20299155_0145a_pricing_catalog_base.py",
    "20299220_0150_partner_core_tables.py",
    "20299290_0157_partner_payout_correlation_id.py",
    "20299360_0164_marketplace_moderation_audit.py",
    "20299610_0170_logistics_fuel_control_v1.py",
    "20299830_0186_client_onboarding_applications.py",
    "20299840_0187_client_documents.py",
    "20299850_0188_onboarding_review_client_link.py",
    "20299860_0189_client_generated_documents.py",
    "20299870_0190_client_doc_signing.py",
    "20299880_0191_client_docflow_packages_notifications.py",
    "20299990_0189_phase3_financial_hardening.py",
    "20300030_0203_otp_challenges_doc_sign.py",
    "20300130_0206_internal_ledger_v1_backbone.py",
    "20300150_0207_service_requests.py",
}


@pytest.fixture(scope="module")
def migrations() -> list[tuple[Path, ast.AST]]:
    files = sorted(MIGRATIONS_DIR.glob("*.py"))
    assert files, "No alembic migration files found"

    parsed = []
    for path in files:
        parsed.append((path, ast.parse(path.read_text(encoding="utf-8"), filename=str(path))))
    return parsed


def _resolve_call_name(func: ast.AST) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _validate_helper_call(name: str, call: ast.Call, path: Path) -> list[str]:
    errors: list[str] = []

    if not call.args or not isinstance(call.args[0], ast.Name) or call.args[0].id != "bind":
        errors.append(f"{path.name}:{call.lineno} {name}() must be called with 'bind' as the first argument")

    min_args = MIN_POSITIONAL[name]
    max_args = MAX_POSITIONAL[name]
    if len(call.args) < min_args:
        errors.append(
            f"{path.name}:{call.lineno} {name}() expects at least {min_args} positional arguments (bind plus required names)"
        )
    if len(call.args) > max_args:
        errors.append(f"{path.name}:{call.lineno} {name}() received too many positional arguments (max {max_args})")

    for keyword in call.keywords:
        if keyword.arg is None:
            errors.append(
                f"{path.name}:{call.lineno} {name}() may only use explicit keywords; '**' expansion is not allowed"
            )
            continue

        if keyword.arg not in ALLOWED_KEYWORDS[name]:
            errors.append(
                f"{path.name}:{call.lineno} {name}() keyword '{keyword.arg}' is not allowed (only 'schema')"
            )

    if name == "index_exists":
        for keyword in call.keywords:
            if keyword.arg == "table_name":
                errors.append(f"{path.name}:{call.lineno} index_exists() must not use 'table_name' keyword")

    return errors


def test_migrations_do_not_define_local_helpers(migrations: list[tuple[Path, ast.AST]]) -> None:
    violations: list[str] = []

    for path, tree in migrations:
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in FORBIDDEN_DEFINITIONS:
                violations.append(f"{path.name}:{node.lineno} defines forbidden helper '{node.name}'")

    assert not violations, "Found forbidden helper definitions:\n" + "\n".join(sorted(violations))


def test_helper_invocations_follow_contract(migrations: list[tuple[Path, ast.AST]]) -> None:
    violations: list[str] = []

    for path, tree in migrations:
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            func_name = _resolve_call_name(node.func)
            if func_name in HELPER_NAMES:
                violations.extend(_validate_helper_call(func_name, node, path))

    assert not violations, "Helper contract violations:\n" + "\n".join(sorted(violations))


def _collect_guard_values(test: ast.AST, target: str) -> list[str]:
    names: list[str] = []

    def _visit(expr: ast.AST) -> None:
        if isinstance(expr, ast.BoolOp) and isinstance(expr.op, ast.And):
            for value in expr.values:
                _visit(value)
            return

        if not (isinstance(expr, ast.UnaryOp) and isinstance(expr.op, ast.Not)):
            return

        call = expr.operand
        if not isinstance(call, ast.Call):
            return

        func_name = _resolve_call_name(call.func)
        if func_name != target and not (
            target == "table_exists" and func_name in {"_table_exists", "table_exists"}
        ):
            return

        if target == "table_exists":
            # table_exists checks historically omitted bind in some migrations.
            arg = call.args[1] if len(call.args) >= 2 else (call.args[0] if call.args else None)
            table_name = arg.value if isinstance(arg, ast.Constant) else None
            if isinstance(table_name, str):
                names.append(table_name)
            return

        if not call.args or not isinstance(call.args[0], ast.Name) or call.args[0].id != "bind":
            return

        if target == "constraint_exists" and len(call.args) >= 3 and isinstance(call.args[2], ast.Constant):
            constraint = call.args[2].value
            if isinstance(constraint, str):
                names.append(constraint)
        elif target == "index_exists" and len(call.args) >= 2 and isinstance(call.args[1], ast.Constant):
            name = call.args[1].value
            if isinstance(name, str):
                names.append(name)

    _visit(test)
    return names


def _extract_literal_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _analyze_upgrade_guards(path: Path, tree: ast.AST) -> list[str]:
    violations: list[str] = []

    class GuardState(ast.NodeVisitor):
        def __init__(self) -> None:
            self.table_guards: list[set[str]] = [set()]
            self.index_guards: list[set[str]] = [set()]
            self.constraint_guards: list[set[str]] = [set()]

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            if node.name != "upgrade":
                return
            for stmt in node.body:
                self._visit_stmt(stmt, self.table_guards[-1], self.index_guards[-1], self.constraint_guards[-1])

        def _visit_stmt(
            self,
            node: ast.stmt,
            table_guard: set[str],
            index_guard: set[str],
            constraint_guard: set[str],
        ) -> None:
            if isinstance(node, ast.If):
                table_names = set(_collect_guard_values(node.test, "table_exists"))
                index_names = set(_collect_guard_values(node.test, "index_exists"))
                constraint_names = set(_collect_guard_values(node.test, "constraint_exists"))

                updated_tables = table_guard | table_names
                updated_indexes = index_guard | index_names
                updated_constraints = constraint_guard | constraint_names

                for stmt in node.body:
                    self._visit_stmt(stmt, updated_tables, updated_indexes, updated_constraints)
                for stmt in node.orelse:
                    self._visit_stmt(stmt, table_guard, index_guard, constraint_guard)
                return

            if isinstance(node, ast.Expr):
                node = node.value  # type: ignore[assignment]

            if isinstance(node, ast.Call):
                func_name = _resolve_call_name(node.func)
                if func_name == "create_table_if_not_exists":
                    return

                if isinstance(node.func, ast.Attribute) and node.func.attr == "create_table":
                    table_name = _extract_literal_string(node.args[0]) if node.args else None
                    if table_name and table_name not in table_guard:
                        violations.append(
                            f"{path.name}:{node.lineno} op.create_table('{table_name}') must be guarded by table_exists"
                        )
                    return

                if isinstance(node.func, ast.Attribute) and node.func.attr == "create_index":
                    index_name = _extract_literal_string(node.args[0]) if node.args else None
                    if index_name and index_name not in index_guard:
                        violations.append(
                            f"{path.name}:{node.lineno} op.create_index('{index_name}') must be guarded by index_exists"
                        )
                    return

                if isinstance(node.func, ast.Attribute) and node.func.attr == "create_unique_constraint":
                    constraint_name = _extract_literal_string(node.args[0]) if node.args else None
                    if constraint_name and constraint_name not in constraint_guard:
                        violations.append(
                            f"{path.name}:{node.lineno} op.create_unique_constraint('{constraint_name}') must be guarded by constraint_exists"
                        )
                    return

            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.stmt):
                    self._visit_stmt(child, table_guard, index_guard, constraint_guard)

    GuardState().visit(tree)
    return violations


def test_upgrade_operations_are_guarded(migrations: list[tuple[Path, ast.AST]]) -> None:
    violations: list[str] = []

    for path, tree in migrations:
        if path.name in LEGACY_UNGUARDED_MIGRATIONS:
            continue
        violations.extend(_analyze_upgrade_guards(path, tree))

    assert not violations, "Unguarded migration operations detected:\n" + "\n".join(sorted(violations))


def test_create_table_does_not_use_sa_enum(migrations: list[tuple[Path, ast.AST]]) -> None:
    violations: list[str] = []

    for path, tree in migrations:
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Attribute) or node.func.attr != "create_table":
                continue

            for child in ast.walk(node):
                if not isinstance(child, ast.Call):
                    continue
                if not isinstance(child.func, ast.Attribute):
                    continue
                if not isinstance(child.func.value, ast.Name) or child.func.value.id != "sa":
                    continue
                if child.func.attr == "Enum":
                    violations.append(
                        f"{path.name}:{child.lineno} op.create_table() must not use sa.Enum; use postgresql.ENUM(..., create_type=False)"
                    )

    assert not violations, "Forbidden sa.Enum usage in create_table detected:\n" + "\n".join(sorted(violations))
