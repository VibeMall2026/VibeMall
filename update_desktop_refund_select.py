#!/usr/bin/env python

file_path = r"Hub\templates\return_request.html"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Define the old refund method section for desktop
old_refund_section = '''                        <!-- Refund Method -->
                        <div class="vm-rp-card">
                            <h3>Refund Method</h3>
                            <div class="vm-rp-refund-methods">
                                {% for value,label in refund_options %}
                                <label class="vm-rp-refund-option">
                                    <input type="radio" name="refund_method" value="{{ value }}" required>
                                    <span>{{ label }}</span>
                                </label>
                                {% endfor %}
                            </div>'''

# Define the new refund method section with hidden select
new_refund_section = '''                        <!-- Refund Method -->
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

# Replace all occurrences
content = content.replace(old_refund_section, new_refund_section)

# Write back
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"✓ Added hidden select element for desktop refund method")
