#!/usr/bin/env python
"""
Clear Python cache files and restart Django
"""

import os
import shutil

def clear_pycache():
    """Remove all __pycache__ directories"""
    print("=" * 60)
    print("Clearing Python Cache")
    print("=" * 60)
    
    count = 0
    for root, dirs, files in os.walk('.'):
        if '__pycache__' in dirs:
            cache_path = os.path.join(root, '__pycache__')
            try:
                shutil.rmtree(cache_path)
                print(f"✅ Removed: {cache_path}")
                count += 1
            except Exception as e:
                print(f"❌ Failed to remove {cache_path}: {e}")
    
    # Also remove .pyc files
    pyc_count = 0
    for root, dirs, files in os.walk('.'):
        for file in files:
            if file.endswith('.pyc'):
                pyc_path = os.path.join(root, file)
                try:
                    os.remove(pyc_path)
                    pyc_count += 1
                except Exception as e:
                    pass
    
    print(f"\n✅ Removed {count} __pycache__ directories")
    print(f"✅ Removed {pyc_count} .pyc files")
    print("=" * 60)
    print("\n🔄 Now restart your Django server:")
    print("   python manage.py runserver")

if __name__ == "__main__":
    clear_pycache()
