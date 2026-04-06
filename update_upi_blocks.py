#!/usr/bin/env python
import re

# Read the file
file_path = r"Hub\templates\return_request.html"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Define the old UPI block pattern
old_upi_block = '''                            <div class="vm-rp-form-group" id="vmRpUpiBlockDesktop" style="display:none;">
                                <label>UPI ID</label>
                                <input type="text" name="upi_id" placeholder="yourname@bank">
                            </div>'''

# Define the new UPI block pattern
new_upi_block = '''                            <div class="vm-rp-form-group" id="vmRpUpiBlockDesktop" style="display:none;">
                                <label>UPI ID</label>
                                <div style="display: flex; gap: 10px; align-items: flex-start;">
                                    <input type="text" name="upi_id" placeholder="yourname@bank" id="vmRpUpiIdDesktop" style="flex: 1;">
                                    <button type="button" class="vm-rp-verify-btn" data-action="verify-upi-desktop" style="padding: 8px 16px; background: #667eea; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 13px; white-space: nowrap; margin-top: 0;">Verify</button>
                                </div>
                                <div id="vmRpUpiVerifyStatusDesktop" style="display: none; margin-top: 10px; padding: 10px; border-radius: 4px; font-size: 13px;"></div>
                                <div id="vmRpUpiNameDesktop" style="display: none; margin-top: 10px; padding: 10px; background: #f0f9ff; border-radius: 4px; border-left: 3px solid #667eea;">
                                    <label style="display: block; margin-bottom: 5px; font-weight: 500;">Verified Account Name</label>
                                    <p id="vmRpUpiNameValueDesktop" style="margin: 0; font-size: 14px; color: #1a202c;"></p>
                                </div>
                            </div>'''

# Replace all occurrences
content = content.replace(old_upi_block, new_upi_block)

# Write the file back
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"✓ Updated return_request.html - Replaced UPI blocks")
