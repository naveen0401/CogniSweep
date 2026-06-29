# CogniSweep Code Review Fixes

This document tracks the review issues found in the CogniSweep codebase and the current status of each correction.

## Completed

1. **Plaintext password fallback in production**
   - Status: Completed.
   - Production authentication blocks plaintext password fallback and requires hashed credentials.

2. **Inconsistent runtime environment access**
   - Status: Completed.
   - Runtime and worker modules now use the shared alias-aware helpers in `app_runtime_config.py`.

3. **Redundant deployment checker helpers**
   - Status: Completed.
   - Shared alias/template helpers now live in `deploy/checker_utils.py`, and `deploy/release_check.py` uses one JSON subcheck wrapper for repeated checker calls.

4. **Silent broad exception handlers**
   - Status: Completed for silent `except Exception: pass` paths.
   - Remaining broad handlers are boundary guards that record failures in logs, smoke reports, or task/error records.

5. **Unused legacy dashboard**
   - Status: Completed.
   - `_legacy_page_dashboard_unused` is no longer present in `app.py`, with regression coverage in `test_auth_password_policy.py`.

6. **Hardcoded launch branch**
   - Status: Completed.
   - `DEPLOY_EXPECTED_BRANCH` is configurable via `ERRORSWEEP_EXPECTED_BRANCH`, defaulting to `main`.

7. **Optional LanguageTool dependency**
   - Status: Completed as documented optional feature.
   - LanguageTool remains intentionally optional for local-only grammar checks; public HTTP routing stays disabled unless explicitly enabled by rules.

## Deferred

1. **Monolithic `app.py` structure**
   - Status: Deferred architectural refactor.
   - The file is still large and should be split gradually into page, auth, config, and styling modules. This needs a dedicated migration plan because `app.py` currently owns many Streamlit session and route contracts.

2. **Environment variable prefix migration**
   - Status: Deferred compatibility migration.
   - The code supports `ERRORSWEEP_` keys with `COGNISWEEP_` aliases. README notes that legacy keys are stable deployment configuration and should not be renamed without a deliberate secrets/docs/runtime migration.
