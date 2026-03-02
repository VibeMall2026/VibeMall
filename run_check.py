#!/usr/bin/env python
import subprocess
import sys

result = subprocess.run([sys.executable, 'manage.py', 'check'], cwd='.', capture_output=True, text=True)
print(result.stdout)
print(result.stderr)
sys.exit(result.returncode)
