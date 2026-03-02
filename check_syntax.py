#!/usr/bin/env python
import py_compile
import sys

try:
    py_compile.compile('Hub/views.py', doraise=True)
    print("✓ Hub/views.py: Syntax OK")
except py_compile.PyCompileError as e:
    print(f"✗ Syntax Error in Hub/views.py:")
    print(e)
    sys.exit(1)

# Try importing to catch runtime errors
try:
    import os
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
    import django
    django.setup()
    from Hub import views
    print("✓ Hub/views.py: Import OK")
except Exception as e:
    print(f"✗ Import Error in Hub/views.py:")
    print(f"{type(e).__name__}: {str(e)[:200]}")
    sys.exit(1)

print("\n✓ All checks passed!")
