import re
import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SCHEMA = ROOT / "supabase_v42_release_schema.sql"
PERSISTENCE = ROOT / "production_persistence.py"
WORKFLOW = ROOT / ".github" / "workflows" / "release-gate.yml"
RELEASE_CHECK = ROOT / "deploy" / "release_check.py"
SCHEMA_CHECK = ROOT / "deploy" / "supabase_schema_check.py"


def source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def production_tables() -> set[str]:
    text = source(PERSISTENCE)
    tree = ast.parse(text)
    saas_tables = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "SAAS_TABLES":
                    saas_tables = ast.literal_eval(node.value)
    return {
        "errorsweep_editor_jobs",
        "errorsweep_usage_events",
        *{str(table) for table in saas_tables.values()},
    }


def test_every_rls_enabled_table_has_policy():
    schema = source(SCHEMA).lower()
    tables = set(re.findall(r"alter\s+table\s+public\.(errorsweep_[a-z0-9_]+)\s+enable\s+row\s+level\s+security", schema))
    policies = set(re.findall(r"create\s+policy\s+[a-z0-9_]+\s+on\s+public\.(errorsweep_[a-z0-9_]+)", schema))

    expected = production_tables()
    assert expected <= tables
    missing = sorted(expected - policies)
    assert not missing, f"RLS-enabled production tables without policies: {missing}"


def test_rls_policies_use_workspace_user_and_platform_helpers():
    schema = source(SCHEMA).lower()

    for token in [
        "create or replace function public.errorsweep_jwt_workspace()",
        "create or replace function public.errorsweep_jwt_email()",
        "create or replace function public.errorsweep_is_platform_owner()",
        "create or replace function public.errorsweep_workspace_matches(row_workspace text)",
        "create or replace function public.errorsweep_email_matches(row_email text)",
        "for all to authenticated",
        "with check",
    ]:
        assert token in schema


def test_schema_and_release_checks_enforce_rls_policy_coverage():
    workflow = source(WORKFLOW)
    release_check = source(RELEASE_CHECK)
    schema_check = source(SCHEMA_CHECK)

    assert "python test_supabase_rls_policies.py" in workflow
    assert "Supabase tenant RLS policy coverage" in release_check
    assert "Supabase tenant RLS policies" in schema_check
    assert "CREATE_POLICY_RE" in schema_check


if __name__ == "__main__":
    test_every_rls_enabled_table_has_policy()
    test_rls_policies_use_workspace_user_and_platform_helpers()
    test_schema_and_release_checks_enforce_rls_policy_coverage()
    print("Supabase RLS policy checks passed.")
