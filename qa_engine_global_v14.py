"""Compatibility shim for older CogniSweep QA engine imports.

The active implementation lives in qa_engine_global_v15. Keeping this module
as a re-export prevents old routes from drifting on duplicated code.
"""

from qa_engine_global_v15 import *  # noqa: F401,F403
import qa_engine_global_v15 as _impl


def __getattr__(name):
    return getattr(_impl, name)
