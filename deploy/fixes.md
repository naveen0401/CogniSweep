# CogniSweep Code Review Fixes

This document outlines the issues found during a review of the CogniSweep codebase and suggests fixes.

## High-Priority Issues

1.  **Monolithic `app.py` Structure**: The `app.py` file is over 5,000 lines long, containing UI, logic, routing, and styling. This makes it extremely difficult to maintain, debug, and test.
    *   **Fix**: Refactor `app.py` into smaller, more focused modules. For example:
        *   `pages/`: A directory containing a separate file for each page renderer (e.g., `pages/dashboard.py`, `pages/projects.py`).
        *   `utils/`: For helper functions like `now_stamp`, `safe_text`, `hash_password`, etc.
        *   `auth.py`: For all authentication, session, and permission-related logic.
        *   `config.py`: For application constants and configuration.
        *   `assets/styles.css`: For all the CSS currently injected via `st.markdown`.

2.  **Plaintext Password Fallback in Production**: The `verify_login_password` function in `app.py` contains a fallback to check plaintext passwords for legacy secrets. Although guarded by `is_production_mode()`, this logic presents a significant security risk and should not exist in production code.
    *   **Fix**: Remove the plaintext password comparison logic entirely from `verify_login_password`. The application should only support hashed passwords in all environments.

3.  **Inconsistent `os.getenv` Usage**: The codebase uses both `os.environ.get()` and `os.getenv()`. The `runtime_env` function in `app.py` is a good pattern, but it's not used consistently. `async_workflow_processor.py` has its own `env_value` implementation.
    *   **Fix**: Consolidate environment variable access into a single utility function (like `runtime_env`) and use it consistently across the entire project to ensure uniform handling of aliases and defaults.

4.  **Redundant Code in Deployment Scripts**: The deployment check scripts (`async_worker_check.py`, `mt_endpoint_check.py`, `release_check.py`) share a lot of boilerplate code for argument parsing, reading env files, and reporting results.
    *   **Fix**: Create a shared `deploy/checker_utils.py` module to house common functions for parsing arguments, reading configuration, and formatting reports to reduce code duplication.

## Medium-Priority Issues

1.  **Broad `except Exception` Clauses**: Many functions use broad `except Exception` blocks, which can hide bugs and make debugging difficult.
    *   **Fix**: Replace generic `except Exception` with more specific exception types (e.g., `ValueError`, `KeyError`, `requests.RequestException`) wherever possible.

2.  **Inconsistent Naming for Environment Variables**: The project uses both `ERRORSWEEP_` and `COGNISWEEP_` prefixes for environment variables. While there's an aliasing function, this adds complexity.
    *   **Fix**: Standardize on a single prefix, preferably `COGNISWEEP_`, and update all documentation, deployment scripts, and code to reflect this.

3.  **Unused `_legacy_page_dashboard_unused` function**: The `app.py` file contains a function named `_legacy_page_dashboard_unused`, which appears to be an older version of the dashboard.
    *   **Fix**: Remove this unused function to clean up the codebase.

4.  **Hardcoded `main` Branch in `app.py`**: The `DEPLOY_EXPECTED_BRANCH` constant is hardcoded to `"main"`. This is not flexible for development or staging branches.
    *   **Fix**: Make this configurable via an environment variable, with `"main"` as the default.

## Low-Priority Issues

1.  **Unused `language_tool_python` Dependency**: The `qa_engine_global_v15.py` file imports `language_tool_python` but the logic to use it seems to be disabled by default. The public HTTP API is used instead.
    *   **Fix**: If the local LanguageTool server is not a planned feature, remove the dependency and the related code to simplify the setup. If it is a feature, ensure the logic is correctly implemented and documented.