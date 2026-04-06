#!/usr/bin/env python

file_path = r"Hub\templates\return_request.html"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Define the old mobile UPI block (in select dropdown - won't have verify button there)
old_mobile_upi_section = '''                <select name="refund_method" id="vmRpRefundMethodMobile" required>
                    {% for value,label in refund_options %}
                    <option value="{{ value }}">{{ label }}</option>
                    {% endfor %}
                </select>'''

# Define the old tablet UPI block (in select dropdown - won't have verify button there)
old_tablet_upi_section = '''                <select name="refund_method" id="vmRpRefundMethodTablet" required>
                    {% for value,label in refund_options %}
                    <option value="{{ value }}">{{ label }}</option>
                    {% endfor %}
                </select>'''

# Old mobile UPI form block
old_mobile_upi_form = '''                    <div class="vm-rp-form-group" id="vmRpUpiBlockMobile" style="display:none;">
                        <label>UPI ID</label>
                        <input type="text" name="upi_id" placeholder="yourname@bank">
                    </div>'''

# New mobile UPI form block with verify button
new_mobile_upi_form = '''                    <div class="vm-rp-form-group" id="vmRpUpiBlockMobile" style="display:none;">
                        <label>UPI ID</label>
                        <div style="display: flex; gap: 8px; align-items: flex-start;">
                            <input type="text" name="upi_id_mobile" placeholder="yourname@bank" id="vmRpUpiIdMobile" style="flex: 1;">
                            <button type="button" class="vm-rp-verify-btn" data-action="verify-upi-mobile" style="padding: 8px 12px; background: #667eea; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 12px; white-space: nowrap;">Verify</button>
                        </div>
                        <div id="vmRpUpiVerifyStatusMobile" style="display: none; margin-top: 8px; padding: 8px; border-radius: 4px; font-size: 12px;"></div>
                        <div id="vmRpUpiNameMobile" style="display: none; margin-top: 8px; padding: 8px; background: #f0f9ff; border-radius: 4px; border-left: 3px solid #667eea;">
                            <label style="display: block; margin-bottom: 3px; font-weight: 500; font-size: 12px;">Verified Name</label>
                            <p id="vmRpUpiNameValueMobile" style="margin: 0; font-size: 12px; color: #1a202c;"></p>
                        </div>
                    </div>'''

# Old tablet UPI form block
old_tablet_upi_form = '''                    <div class="vm-rp-form-group" id="vmRpUpiBlockTablet" style="display:none;">
                        <label>UPI ID</label>
                        <input type="text" name="upi_id" placeholder="yourname@bank">
                    </div>'''

# New tablet UPI form block with verify button
new_tablet_upi_form = '''                    <div class="vm-rp-form-group" id="vmRpUpiBlockTablet" style="display:none;">
                        <label>UPI ID</label>
                        <div style="display: flex; gap: 8px; align-items: flex-start;">
                            <input type="text" name="upi_id_tablet" placeholder="yourname@bank" id="vmRpUpiIdTablet" style="flex: 1;">
                            <button type="button" class="vm-rp-verify-btn" data-action="verify-upi-tablet" style="padding: 8px 14px; background: #667eea; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 13px; white-space: nowrap;">Verify</button>
                        </div>
                        <div id="vmRpUpiVerifyStatusTablet" style="display: none; margin-top: 8px; padding: 8px; border-radius: 4px; font-size: 12px;"></div>
                        <div id="vmRpUpiNameTablet" style="display: none; margin-top: 8px; padding: 8px; background: #f0f9ff; border-radius: 4px; border-left: 3px solid #667eea;">
                            <label style="display: block; margin-bottom: 3px; font-weight: 500; font-size: 13px;">Verified Name</label>
                            <p id="vmRpUpiNameValueTablet" style="margin: 0; font-size: 13px; color: #1a202c;"></p>
                        </div>
                    </div>'''

# Replace all occurrences
content = content.replace(old_mobile_upi_form, new_mobile_upi_form)
content = content.replace(old_tablet_upi_form, new_tablet_upi_form)

# Write back
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("✓ Updated mobile and tablet UPI blocks with verify button")
