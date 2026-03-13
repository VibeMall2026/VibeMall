#!/usr/bin/env python
"""
Simple migration runner script
"""

import os
import sys
import subprocess

def run_command(command, description):
    """Run a command and handle output"""
    print(f"\n🔧 {description}")
    print("=" * 50)
    
    try:
        # Run command with proper environment
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        if result.stdout:
            print("STDOUT:")
            print(result.stdout)
        
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
        
        if result.returncode == 0:
            print(f"✅ {description} completed successfully!")
            return True
        else:
            print(f"⚠️ {description} completed with warnings (exit code: {result.returncode})")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"⏰ {description} timed out after 5 minutes")
        return False
    except Exception as e:
        print(f"❌ {description} failed: {e}")
        return False

def main():
    print("🚀 Django Migration Runner")
    print("=" * 40)
    
    # Set environment variables
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')
    
    # Commands to run
    commands = [
        ("python manage.py check --deploy", "Django System Check"),
        ("python manage.py makemigrations Hub", "Create Migrations"),
        ("python manage.py migrate", "Apply Migrations"),
        ("python manage.py check", "Final System Check"),
    ]
    
    success_count = 0
    
    for command, description in commands:
        if run_command(command, description):
            success_count += 1
    
    print(f"\n📊 SUMMARY")
    print("=" * 20)
    print(f"✅ Successful: {success_count}/{len(commands)}")
    print(f"⚠️ Issues: {len(commands) - success_count}/{len(commands)}")
    
    if success_count == len(commands):
        print("\n🎉 All migrations completed successfully!")
        print("🌐 Your comprehensive features are now ready!")
        print("📍 Access admin panel at: /admin-panel/")
    else:
        print("\n⚠️ Some commands had issues, but this may be normal during development.")
        print("🔍 Check the output above for details.")
    
    return success_count == len(commands)

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)