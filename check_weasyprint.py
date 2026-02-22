#!/usr/bin/env python
"""
Quick script to check if WeasyPrint is installed and working
Run this before testing registration to ensure PDF generation will work
"""

import sys

def check_weasyprint():
    """Check if WeasyPrint is installed and can generate PDFs"""
    print("=" * 60)
    print("WeasyPrint Installation Check")
    print("=" * 60)
    
    # Check if weasyprint is installed
    try:
        import weasyprint
        print("✅ WeasyPrint is installed")
        print(f"   Version: {weasyprint.__version__}")
    except ImportError as e:
        print("❌ WeasyPrint is NOT installed")
        print(f"   Error: {e}")
        print("\n📦 To install WeasyPrint:")
        print("   pip install weasyprint")
        print("\n⚠️  On Windows, you may need GTK3 runtime:")
        print("   Download from: https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases")
        return False
    
    # Try to generate a simple PDF
    try:
        from weasyprint import HTML
        from io import BytesIO
        
        print("\n🔄 Testing PDF generation...")
        
        html_content = """
        <!DOCTYPE html>
        <html>
        <head><title>Test</title></head>
        <body>
            <h1>WeasyPrint Test</h1>
            <p>If you can see this PDF, WeasyPrint is working correctly!</p>
        </body>
        </html>
        """
        
        pdf_file = BytesIO()
        HTML(string=html_content).write_pdf(pdf_file)
        pdf_size = len(pdf_file.getvalue())
        
        print(f"✅ PDF generation successful!")
        print(f"   Generated PDF size: {pdf_size} bytes")
        
        # Save test PDF
        with open('test_weasyprint.pdf', 'wb') as f:
            f.write(pdf_file.getvalue())
        print(f"   Test PDF saved as: test_weasyprint.pdf")
        
    except Exception as e:
        print(f"❌ PDF generation failed!")
        print(f"   Error: {e}")
        print("\n⚠️  This usually means GTK3 runtime is not installed on Windows")
        print("   Download from: https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases")
        return False
    
    print("\n" + "=" * 60)
    print("✅ All checks passed! WeasyPrint is ready to use.")
    print("=" * 60)
    print("\n📧 Welcome emails will include Terms & Conditions PDF attachment")
    print("🚀 You can now test user registration")
    
    return True


if __name__ == "__main__":
    success = check_weasyprint()
    sys.exit(0 if success else 1)
