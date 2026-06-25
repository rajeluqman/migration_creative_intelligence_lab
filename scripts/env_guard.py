"""Fail-closed env guard (ported from the sibling repo's S3 guard → OneLake, ADR-008).
Import + call assert_safe() in any runner that touches OneLake, so a misconfigured env aborts
instead of writing to the wrong workspace/lakehouse."""
import os
import sys


def assert_safe():
    workspace = os.getenv("FABRIC_WORKSPACE", "")
    lakehouse = os.getenv("FABRIC_LAKEHOUSE", "")
    if not workspace:
        sys.exit("env_guard: FABRIC_WORKSPACE unset - refusing to run.")
    if not lakehouse:
        sys.exit("env_guard: FABRIC_LAKEHOUSE unset - refusing to run.")
    # Extend: in a drill/incubator context require a throwaway workspace, never the canonical one.


if __name__ == "__main__":
    assert_safe()
    print("env_guard: ok")
