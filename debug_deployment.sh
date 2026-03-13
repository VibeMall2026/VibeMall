#!/bin/bash

# 🔧 VibeMall Deployment Debug Script
# This script helps diagnose deployment issues

set -e

echo "🔧 VibeMall Deployment Debug Script"
echo "=================================="
echo "📅 Started at: $(date)"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running on VPS or local
if [ -d "/var/www/vibemall" ]; then
    print_status "Running on VPS - performing full diagnostic"
    ON_VPS=true
else
    print_status "Running locally - performing local checks"
    ON_VPS=false
fi

echo ""
echo "🔍 SYSTEM INFORMATION"
echo "===================="
print_status "Hostname: $(hostname)"
print_status "User: $(whoami)"
print_status "OS: $(uname -a)"
print_status "Current directory: $(pwd)"

if [ "$ON_VPS" = true ]; then
    echo ""
    echo "🌐 NETWORK & SSH CHECKS"
    echo "======================"
    
    # Check SSH service
    if systemctl is-active --quiet ssh; then
        print_success "SSH service is running"
    else
        print_error "SSH service is not running"
        print_status "Attempting to start SSH service..."
        sudo systemctl start ssh || print_error "Failed to start SSH service"
    fi
    
    # Check SSH configuration
    if [ -f "/etc/ssh/sshd_config" ]; then
        print_status "SSH configuration exists"
        SSH_PORT=$(grep "^Port" /etc/ssh/sshd_config | awk '{print $2}' || echo "22")
        print_status "SSH Port: $SSH_PORT"
    fi
    
    # Check firewall
    if command -v ufw >/dev/null 2>&1; then
        UFW_STATUS=$(sudo ufw status | head -1)
        print_status "Firewall status: $UFW_STATUS"
    fi
fi

echo ""
echo "📂 PROJECT DIRECTORY CHECKS"
echo "==========================="

if [ "$ON_VPS" = true ]; then
    PROJECT_DIR="/var/www/vibemall"
else
    PROJECT_DIR="."
fi

if [ -d "$PROJECT_DIR" ]; then
    print_success "Project directory exists: $PROJECT_DIR"
    cd "$PROJECT_DIR"
    
    # Check git repository
    if [ -d ".git" ]; then
        print_success "Git repository detected"
        print_status "Current branch: $(git branch --show-current 2>/dev/null || echo 'unknown')"
        print_status "Last commit: $(git log --oneline -1 2>/dev/null || echo 'unknown')"
        
        # Check for uncommitted changes
        if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
            print_warning "Uncommitted changes detected"
            git status --porcelain
        else
            print_success "Working directory is clean"
        fi
    else
        print_error "Not a git repository"
    fi
    
    # Check important files
    FILES_TO_CHECK=("manage.py" "requirements.txt" "VibeMall/settings.py" ".env")
    for file in "${FILES_TO_CHECK[@]}"; do
        if [ -f "$file" ]; then
            print_success "$file exists"
        else
            print_error "$file is missing"
        fi
    done
    
else
    print_error "Project directory not found: $PROJECT_DIR"
    exit 1
fi

echo ""
echo "🐍 PYTHON ENVIRONMENT CHECKS"
echo "============================"

# Check Python version
if command -v python >/dev/null 2>&1; then
    PYTHON_VERSION=$(python --version)
    print_status "Python version: $PYTHON_VERSION"
else
    print_error "Python not found in PATH"
fi

# Check virtual environment
if [ "$ON_VPS" = true ]; then
    VENV_PATH="venv/bin/activate"
else
    VENV_PATH="venv/bin/activate"
fi

if [ -f "$VENV_PATH" ]; then
    print_success "Virtual environment found"
    
    # Activate and check
    source "$VENV_PATH"
    print_status "Activated virtual environment"
    print_status "Python in venv: $(which python)"
    print_status "Pip version: $(pip --version)"
    
    # Check Django installation
    if python -c "import django" 2>/dev/null; then
        DJANGO_VERSION=$(python -c "import django; print(django.get_version())")
        print_success "Django installed: $DJANGO_VERSION"
    else
        print_error "Django not installed in virtual environment"
    fi
    
else
    print_error "Virtual environment not found at $VENV_PATH"
fi

if [ "$ON_VPS" = true ]; then
    echo ""
    echo "🔧 SERVICE CHECKS"
    echo "================"
    
    # Check VibeMall service
    if systemctl is-active --quiet vibemall; then
        print_success "VibeMall service is running"
    else
        print_error "VibeMall service is not running"
        print_status "Service status:"
        sudo systemctl status vibemall --no-pager || true
    fi
    
    # Check Nginx service
    if systemctl is-active --quiet nginx; then
        print_success "Nginx service is running"
    else
        print_error "Nginx service is not running"
        print_status "Service status:"
        sudo systemctl status nginx --no-pager || true
    fi
    
    echo ""
    echo "📊 SYSTEM RESOURCES"
    echo "=================="
    
    # Check disk space
    print_status "Disk usage:"
    df -h / || true
    
    # Check memory
    print_status "Memory usage:"
    free -h || true
    
    # Check load average
    print_status "Load average: $(uptime | awk -F'load average:' '{print $2}')"
fi

echo ""
echo "🧪 DJANGO CHECKS"
echo "================"

if [ -f "manage.py" ] && [ -f "$VENV_PATH" ]; then
    source "$VENV_PATH"
    
    # Basic Django check
    print_status "Running Django system check..."
    if python manage.py check --verbosity=0; then
        print_success "Django system check passed"
    else
        print_warning "Django system check found issues"
    fi
    
    # Check migrations
    print_status "Checking migrations..."
    python manage.py showmigrations --verbosity=0 | tail -10 || print_warning "Could not check migrations"
    
else
    print_warning "Skipping Django checks (manage.py or venv not found)"
fi

echo ""
echo "📋 SUMMARY"
echo "=========="
print_status "Debug script completed at: $(date)"

if [ "$ON_VPS" = true ]; then
    echo ""
    print_status "🚀 To manually deploy, run:"
    echo "cd /var/www/vibemall"
    echo "git pull origin main"
    echo "source venv/bin/activate"
    echo "pip install -r requirements.txt"
    echo "python manage.py makemigrations --merge"
    echo "python manage.py migrate"
    echo "python manage.py collectstatic --noinput"
    echo "sudo systemctl restart vibemall"
    echo "sudo systemctl reload nginx"
else
    echo ""
    print_status "🔍 To test deployment locally:"
    echo "python manage.py check"
    echo "python manage.py makemigrations --dry-run"
    echo "python manage.py test --verbosity=2"
fi

echo ""
print_success "Debug script finished!"