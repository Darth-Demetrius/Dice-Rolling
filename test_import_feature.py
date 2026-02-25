#!/usr/bin/env python3
"""Test script for the --import feature of safe_repl.py"""

import subprocess
import sys

def test_import(import_spec, test_code, expected_output=None):
    """Test an import specification with some code."""
    print(f"\n{'='*60}")
    print(f"Testing: --import '{import_spec}'")
    print(f"Code: {test_code}")
    print(f"{'='*60}")

    cmd = [
        sys.executable,
        "safe_repl.py",
        "--import", import_spec
    ]

    try:
        result = subprocess.run(
            cmd,
            input=f"{test_code}\nquit\n",
            capture_output=True,
            text=True,
            timeout=5
        )

        print("STDERR:", result.stderr.strip() if result.stderr.strip() else "(none)")
        print("STDOUT:", result.stdout)

        if expected_output and expected_output in result.stdout:
            print("✓ PASS")
        elif expected_output:
            print(f"✗ FAIL: Expected '{expected_output}' in output")

        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print("✗ TIMEOUT")
        return False
    except Exception as e:
        print(f"✗ ERROR: {e}")
        return False

if __name__ == "__main__":
    print("Testing --import feature")

    # Test 1: Simple import
    test_import("json", "json.dumps({'a': 1})")

    # Test 2: Import with alias
    test_import("json as j", "j.dumps({'b': 2})")

    # Test 3: From import
    test_import("json:dumps", "dumps({'c': 3})")

    # Test 4: From import with alias
    test_import("json:dumps as d", "d({'d': 4})")

    # Test 5: Multiple from imports
    test_import("json:dumps, loads", "loads(dumps({'e': 5}))")

    print("\n" + "="*60)
    print("All tests completed!")
