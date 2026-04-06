#!/usr/bin/env python
"""
Add JavaScript functions for:
1. Toggle refund fields (bank/upi) on radio selection
2. Improve refund summary calculation
"""

file_path = r"Hub\templates\return_request.html"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Find the point where we initialize sections and add our functions
insertion_point = content.find("    // Initialize all sections\n    sections.forEach(bindSection);")

if insertion_point != -1:
    new_functions = '''
    // ===== DESKTOP SPECIFIC FUNCTIONS =====
    
    // Toggle refund fields based on selection
    window.toggleRefundFieldsDesktop = function() {
        const refundMethod = document.querySelector('input[name="refund_method"]:checked');
        const bankBlock = document.getElementById('vmRpBankBlockDesktop');
        const upiBlock = document.getElementById('vmRpUpiBlockDesktop');
        
        if (!refundMethod) return;
        
        const method = refundMethod.value.toLowerCase();
        
        // Hide all
        if (bankBlock) bankBlock.style.display = 'none';
        if (upiBlock) upiBlock.style.display = 'none';
        
        // Show selected
        if (method === 'bank') {
            if (bankBlock) bankBlock.style.display = 'block';
        } else if (method === 'upi') {
            if (upiBlock) upiBlock.style.display = 'block';
        }
    };
    
    // Initialize desktop refund method listeners
    const desktopRefundRadios = document.querySelectorAll('#vmRpRefundMethodsDesktop input[type="radio"]');
    desktopRefundRadios.forEach((radio) => {
        radio.addEventListener('change', toggleRefundFieldsDesktop);
    });
    
    // Attach UPI verify button listener
    const upiVerifyBtn = document.getElementById('vmRpUpiVerifyBtnDesktop');
    if (upiVerifyBtn) {
        upiVerifyBtn.addEventListener('click', verifyUPIDesktop);
    }
    
    // UPI verification function
    async function verifyUPIDesktop(e) {
        e.preventDefault();
        const upiInput = document.getElementById('vmRpUpiIdDesktop');
        const statusDiv = document.getElementById('vmRpUpiVerifyStatusDesktop');
        const nameDiv = document.getElementById('vmRpUpiNameDesktop');
        const nameValue = document.getElementById('vmRpUpiNameValueDesktop');
        const btn = e.target;
        
        if (!upiInput.value.trim()) {
            statusDiv.style.display = 'block';
            statusDiv.style.background = '#fee';
            statusDiv.style.color = '#c33';
            statusDiv.textContent = '⚠ Please enter a UPI ID';
            return;
        }
        
        btn.disabled = true;
        btn.textContent = 'Verifying...';
        statusDiv.style.display = 'block';
        statusDiv.style.background = '#eef';
        statusDiv.style.color = '#333';
        statusDiv.textContent = '🔄 Verifying UPI ID...';
        
        try {
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
            const response = await fetch('/verify-upi/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ upi_id: upiInput.value.trim() })
            });
            
            const data = await response.json();
            
            if (data.valid) {
                statusDiv.style.display = 'none';
                nameDiv.style.display = 'block';
                nameValue.textContent = data.name || 'Account Verified';
                upiInput.disabled = true;
                btn.textContent = '✓ Verified';
                btn.style.background = '#10b981';
            } else {
                statusDiv.style.display = 'block';
                statusDiv.style.background = '#fee';
                statusDiv.style.color = '#c33';
                statusDiv.textContent = '❌ Invalid UPI ID: ' + (data.error || 'Please check and try again.');
                nameDiv.style.display = 'none';
            }
        } catch (err) {
            statusDiv.style.display = 'block';
            statusDiv.style.background = '#fee';
            statusDiv.style.color = '#c33';
            statusDiv.textContent = '❌ Verification failed. Please try again.';
            console.error('UPI verification error:', err);
        }
        
        btn.disabled = false;
    }
    
    // Initialize on page load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', toggleRefundFieldsDesktop);
    } else {
        toggleRefundFieldsDesktop();
    }

    '''
    
    # Insert before "Initialize all sections"
    content = content[:insertion_point] + new_functions + "\n    " + content[insertion_point:]

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("✓ Added desktop refund field toggle functions")
print("✓ Added UPI verification handler")
print("✓ Initialization updated")
