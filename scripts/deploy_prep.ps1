$ErrorActionPreference = "Stop"

$python = "D:/Iu University/OneDrive - IU International University of Applied Sciences/Desktop/VibeMall/venv/Scripts/python.exe"

Write-Host "Running Django system checks..."
& $python manage.py check

Write-Host "Checking for missing migrations..."
& $python manage.py makemigrations --check --dry-run

Write-Host "Applying migrations..."
& $python manage.py migrate

Write-Host "Collecting static files..."
& $python manage.py collectstatic --noinput

Write-Host "Done. If you need a superuser, run:"
Write-Host "  $python manage.py createsuperuser"
