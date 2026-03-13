#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/var/www/vibemall}"
DEPLOY_BRANCH="${DEPLOY_BRANCH:-main}"
VENV_PATH="${VENV_PATH:-venv/bin/activate}"
SERVICE_NAME="${SERVICE_NAME:-vibemall}"
NGINX_SERVICE="${NGINX_SERVICE:-nginx}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
STASH_NAME="pre-deploy-${TIMESTAMP}"

echo "Starting deployment to VPS..."
echo "Deployment started at: $(date)"
echo "Server: $(hostname)"
echo "User: $(whoami)"

if [ ! -d "$PROJECT_DIR" ]; then
  echo "Project directory not found: $PROJECT_DIR"
  exit 1
fi

cd "$PROJECT_DIR"
echo "Project directory: $(pwd)"

echo "Current git status:"
git status --short || true
git log --oneline -5 || true

echo "Fetching latest changes from origin/${DEPLOY_BRANCH}..."
git fetch origin "$DEPLOY_BRANCH"

if [ -n "$(git status --porcelain)" ]; then
  echo "Local repository changes detected on the server."
  echo "Stashing tracked and untracked changes before deploy as ${STASH_NAME}."
  git stash push --include-untracked --message "$STASH_NAME" >/dev/null
fi

echo "Pulling latest code..."
git pull --ff-only origin "$DEPLOY_BRANCH"

if [ ! -f "$VENV_PATH" ]; then
  echo "Virtual environment not found at $VENV_PATH"
  exit 1
fi

echo "Activating virtual environment..."
# shellcheck disable=SC1090
source "$VENV_PATH"
python --version
pip --version

echo "Installing dependencies..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "Checking for missing committed migrations..."
if ! python manage.py makemigrations --check --dry-run --noinput; then
  echo "Deployment stopped: model changes exist without committed migrations."
  echo "Create and commit migrations locally, then deploy again."
  exit 1
fi

echo "Applying migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Running Django checks..."
python manage.py check || {
  echo "Django check reported issues."
}

echo "Restarting application service..."
sudo systemctl restart "$SERVICE_NAME"
sleep 5

echo "Reloading nginx..."
sudo systemctl reload "$NGINX_SERVICE"

echo "Checking service status..."
sudo systemctl is-active "$SERVICE_NAME" >/dev/null || {
  echo "Service failed to start: $SERVICE_NAME"
  sudo systemctl status "$SERVICE_NAME" --no-pager || true
  exit 1
}

sudo systemctl is-active "$NGINX_SERVICE" >/dev/null || {
  echo "Service is not running: $NGINX_SERVICE"
  sudo systemctl status "$NGINX_SERVICE" --no-pager || true
  exit 1
}

echo "Deployment completed successfully at: $(date)"
