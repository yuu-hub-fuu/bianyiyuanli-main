#!/usr/bin/env python
"""Test Git panel functionality without GUI."""

import sys
from pathlib import Path

# Test 1: Import the module
try:
    from nexa.ide.app import NexaStudio
    print("[OK] Module imported successfully")
except Exception as e:
    print(f"[FAIL] Import error: {e}")
    sys.exit(1)

# Test 2: Check Git-related attributes
try:
    import inspect
    source = inspect.getsource(NexaStudio)

    required_methods = [
        '_show_left_panel',
        '_build_git_panel',
        '_refresh_git_status',
        '_detect_git_repo',
        '_git_commit',
        '_git_push',
        '_git_pull',
        '_git_sync',
    ]

    missing = []
    for method in required_methods:
        if f'def {method}' not in source:
            missing.append(method)

    if missing:
        print(f"[FAIL] Missing methods: {missing}")
        sys.exit(1)

    print("[OK] All required Git methods found")
except Exception as e:
    print(f"[FAIL] Method check error: {e}")
    sys.exit(1)

# Test 3: Check Git panel UI structure
try:
    # Check if the class has required language keys
    from nexa.ide.app import LANG

    git_keys = [
        'source_control',
        'git_branch',
        'git_changes',
        'git_staged',
        'git_unstaged',
        'git_commit',
        'git_commit_msg',
        'git_push',
        'git_pull',
        'git_refresh',
    ]

    lang = LANG.get('zh', {})
    missing_keys = []
    for key in git_keys:
        if key not in lang:
            missing_keys.append(key)

    if missing_keys:
        print(f"[FAIL] Missing language keys: {missing_keys}")
        sys.exit(1)

    print("[OK] All Git language keys found")
except Exception as e:
    print(f"[FAIL] Language key check error: {e}")
    sys.exit(1)

# Test 4: Verify Git command detection
try:
    import subprocess
    result = subprocess.run(['git', '--version'], capture_output=True,
                          timeout=2, check=False)
    if result.returncode == 0:
        print(f"[OK] Git is installed: {result.stdout.decode().strip()}")
    else:
        print("[WARN] Git not found in PATH (optional feature)")
except Exception as e:
    print(f"[WARN] Git check failed: {e} (optional feature)")

print("\n[SUCCESS] All Git panel tests passed!")
