#!/usr/bin/env bash
set -euo pipefail

PYTHON="D:/Iu University/OneDrive - IU International University of Applied Sciences/Desktop/VibeMall/venv/Scripts/python.exe"

$PYTHON manage.py check
$PYTHON manage.py makemigrations --check --dry-run
$PYTHON manage.py migrate
$PYTHON manage.py collectstatic --noinput

echo "Done. If you need a superuser, run:"
echo "  $PYTHON manage.py createsuperuser"
