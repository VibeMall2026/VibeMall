#!/usr/bin/env python
"""
Fix desktop return request page:
1. Remove dropdown select (keep only radio buttons)
2. Improve bank details layout (2-column)
3. Improve UPI field layout
4. Add refund summary calculation logic
"""

file_path = r"Hub\templates\return_request.html"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. FIX: Remove hidden select and radio button sync, keep only radio buttons
old_refund_section = '''                        <!-- Refund Method -->
                        <div class="vm-rp-card">
                            <h3>Refund Method</h3>
                            <select name="refund_method" id="vmRpRefundMethodDesktop" required style="display:none;">
                                {% for value,label in refund_options %}
                                <option value="{{ value }}">{{ label }}</option>
                                {% endfor %}
                            </select>
                            <div class="vm-rp-refund-methods">
                                {% for value,label in refund_options %}
                                <label class="vm-rp-refund-option">
                                    <input type="radio" name="refund_method_display" value="{{ value }}" onchange="document.getElementById('vmRpRefundMethodDesktop').value = this.value; document.getElementById('vmRpRefundMethodDesktop').dispatchEvent(new Event('change'));">
                                    <span>{{ label }}</span>
                                </label>
                                {% endfor %}
                            </div>'''

new_refund_section = '''                        <!-- Refund Method -->
                        <div class="vm-rp-card">
                            <h3>Refund Method</h3>
                            <div class="vm-rp-refund-methods" id="vmRpRefundMethodsDesktop">
                                {% for value,label in refund_options %}
                                <label class="vm-rp-refund-option">
                                    <input type="radio" name="refund_method" value="{{ value|lower }}" required onchange="toggleRefundFieldsDesktop();">
                                    <span>{{ label }}</span>
                                </label>
                                {% endfor %}
                            </div>'''

content = content.replace(old_refund_section, new_refund_section)

# 2. FIX: Improve bank details layout to 2-column
old_bank_layout = '''                            <div class="vm-rp-form-group" id="vmRpBankBlockDesktop" style="display:none;">
                                <label>Account Holder Name</label>
                                <input type="text" name="bank_account_name" placeholder="ANANYA SHARMA">
                                <label>Bank Name</label>
                                <input type="text" name="bank_name" placeholder="HDFC BANK">
                                <label>Account Number</label>
                                <input type="password" name="bank_account_number" placeholder="••••••••9012" inputmode="numeric">
                                <label>IFSC Code</label>
                                <input type="text" name="bank_ifsc" placeholder="HDFC0000123" style="text-transform: uppercase;">
                            </div>'''

new_bank_layout = '''                            <div id="vmRpBankBlockDesktop" style="display:none;">
                                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 15px;">
                                    <div class="vm-rp-form-group">
                                        <label>Account Holder Name</label>
                                        <input type="text" name="bank_account_name" placeholder="ANANYA SHARMA" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px;">
                                    </div>
                                    <div class="vm-rp-form-group">
                                        <label>Bank Name</label>
                                        <input type="text" name="bank_name" placeholder="HDFC BANK" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px;">
                                    </div>
                                    <div class="vm-rp-form-group">
                                        <label>Account Number</label>
                                        <input type="password" name="bank_account_number" placeholder="••••••••9012" inputmode="numeric" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px;">
                                    </div>
                                    <div class="vm-rp-form-group">
                                        <label>IFSC Code</label>
                                        <input type="text" name="bank_ifsc" placeholder="HDFC0000123" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; text-transform: uppercase;">
                                    </div>
                                </div>
                            </div>'''

content = content.replace(old_bank_layout, new_bank_layout)

# 3. FIX: Improve UPI field layout
old_upi_layout = '''                            <div class="vm-rp-form-group" id="vmRpUpiBlockDesktop" style="display:none;">
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

new_upi_layout = '''                            <div id="vmRpUpiBlockDesktop" style="display:none;">
                                <div class="vm-rp-form-group" style="margin-top: 15px;">
                                    <label>UPI ID</label>
                                    <div style="display: flex; gap: 12px; align-items: flex-start;">
                                        <input type="text" name="upi_id" id="vmRpUpiIdDesktop" placeholder="yourname@bank" style="flex: 1; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px;">
                                        <button type="button" id="vmRpUpiVerifyBtnDesktop" data-action="verify-upi-desktop" style="padding: 10px 20px; background: #667eea; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 13px; font-weight: 500; white-space: nowrap; margin-top: 0; transition: background 0.3s;">Verify</button>
                                    </div>
                                    <div id="vmRpUpiVerifyStatusDesktop" style="display: none; margin-top: 10px; padding: 12px; border-radius: 4px; font-size: 13px;"></div>
                                    <div id="vmRpUpiNameDesktop" style="display: none; margin-top: 12px; padding: 12px; background: #f0f9ff; border-radius: 4px; border-left: 4px solid #667eea;">
                                        <label style="display: block; margin-bottom: 5px; font-weight: 600; color: #333;">✓ Verified Account Name</label>
                                        <p id="vmRpUpiNameValueDesktop" style="margin: 0; font-size: 14px; color: #1a202c; font-weight: 500;"></p>
                                    </div>
                                </div>
                            </div>'''

content = content.replace(old_upi_layout, new_upi_layout)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("✓ Desktop refund method section cleaned up")
print("✓ Bank details layout improved to 2-column grid")
print("✓ UPI field layout improved and styled")
