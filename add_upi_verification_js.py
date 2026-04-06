#!/usr/bin/env python

file_path = r"Hub\templates\return_request.html"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Find the location to insert the UPI verification code
# We'll insert it before the closing of the bindSection function

upi_verification_code = '''
        // Handle UPI verification button
        const verifyButtons = document.querySelectorAll('[data-action^="verify-upi"]');
        verifyButtons.forEach((btn) => {
            btn.addEventListener('click', async (e) => {
                e.preventDefault();
                const deviceType = btn.dataset.action.replace('verify-upi-', '').toLowerCase();
                const upiIdInput = document.getElementById(`vmRpUpiId${deviceType.charAt(0).toUpperCase() + deviceType.slice(1)}`);
                const statusDiv = document.getElementById(`vmRpUpiVerifyStatus${deviceType.charAt(0).toUpperCase() + deviceType.slice(1)}`);
                const nameDiv = document.getElementById(`vmRpUpiName${deviceType.charAt(0).toUpperCase() + deviceType.slice(1)}`);
                const nameValue = document.getElementById(`vmRpUpiNameValue${deviceType.charAt(0).toUpperCase() + deviceType.slice(1)}`);
                
                if (!upiIdInput || !upiIdInput.value.trim()) {
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
                statusDiv.textContent = '🔄 Verifying UPI ID...';
                
                try {
                    const response = await fetch('/verify-upi/', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                        },
                        body: JSON.stringify({ upi_id: upiIdInput.value.trim() })
                    });
                    
                    const data = await response.json();
                    
                    if (data.valid) {
                        statusDiv.style.display = 'none';
                        nameDiv.style.display = 'block';
                        nameValue.textContent = data.name || 'Account Verified';
                        upiIdInput.disabled = true;
                        btn.textContent = '✓ Verified';
                    } else {
                        statusDiv.style.display = 'block';
                        statusDiv.style.background = '#fee';
                        statusDiv.style.color = '#c33';
                        statusDiv.textContent = '❌ Invalid UPI ID. Please check and try again.';
                        nameDiv.style.display = 'none';
                    }
                } catch (err) {
                    statusDiv.style.display = 'block';
                    statusDiv.style.background = '#fee';
                    statusDiv.style.color = '#c33';
                    statusDiv.textContent = '❌ Verification failed. Please try again later.';
                    console.error('UPI verification error:', err);
                }
                
                btn.disabled = false;
                btn.textContent = nameDiv.style.display === 'block' ? '✓ Verified' : 'Verify';
            });
        });
'''

# Find the insertion point - just before the closing of the bindSection function
insertion_point = content.rfind('        // Initial summary calculation')
if insertion_point != -1:
    # Insert the UPI verification code before "Initial summary calculation"
    content = content[:insertion_point] + upi_verification_code + '\n        ' + content[insertion_point:]

# Write back
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"✓ Added UPI verification JavaScript handler")
