"""
Script to add JavaScript handlers for:
1. Bank Account Verification (₹1 penny drop)
2. UPI Collect Request (₹1 verification)
3. Refund Processing
"""
import os
import re

template_path = 'Hub/templates/return_request.html'

# Read the template
with open(template_path, 'r', encoding='utf-8') as f:
    content = f.read()

# JavaScript code to add (comprehensive handlers for all 3 features)
new_js_code = '''

    // ===================================================================
    // BANK VERIFICATION HANDLERS - Penny Drop Verification
    // ===================================================================
    
    async function verifyBankAccount(e) {
        e.preventDefault();
        
        const accountNum = document.getElementById('bankAccountNumber')?.value || '';
        const ifscCode = document.getElementById('bankIFSC')?.value || '';
        const accountName = document.getElementById('bankAccountName')?.value || '';
        const statusDiv = document.getElementById('bankVerifyStatus');
        const btn = e.target;
        
        if (!accountNum || !ifscCode) {
            if (statusDiv) {
                statusDiv.style.display = 'block';
                statusDiv.style.background = '#fee';
                statusDiv.style.color = '#c33';
                statusDiv.textContent = '⚠ Account number and IFSC are required';
            }
            return;
        }
        
        btn.disabled = true;
        btn.textContent = 'Verifying...';
        if (statusDiv) {
            statusDiv.style.display = 'block';
            statusDiv.style.background = '#eef';
            statusDiv.style.color = '#333';
            statusDiv.textContent = '🔄 Verifying bank account (₹1 test transfer initiated)...';
        }
        
        try {
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
            if (!csrfToken) throw new Error('CSRF token not found');
            
            const response = await fetch('/api/verify-bank/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({
                    account_number: accountNum,
                    ifsc: ifscCode,
                    account_name: accountName
                })
            });
            
            const data = await response.json();
            console.log('Bank Verification Response:', data);
            
            if (data.status === 'verified') {
                if (statusDiv) {
                    statusDiv.style.background = '#efe';
                    statusDiv.style.color = '#3c3';
                    statusDiv.textContent = `✅ Verified! Name: ${data.account_name}`;
                }
                document.getElementById('bankAccountNumber').disabled = true;
                document.getElementById('bankIFSC').disabled = true;
                btn.textContent = '✓ Verified';
                btn.style.background = '#10b981';
            } else {
                if (statusDiv) {
                    statusDiv.style.background = '#fee';
                    statusDiv.style.color = '#c33';
                    statusDiv.textContent = `❌ ${data.message || 'Verification failed'}`;
                }
            }
        } catch (err) {
            console.error('Bank verification error:', err);
            if (statusDiv) {
                statusDiv.style.background = '#fee';
                statusDiv.style.color = '#c33';
                statusDiv.textContent = `❌ Error: ${err.message}`;
            }
        }
        
        btn.disabled = false;
    }
    
    // ===================================================================
    // UPI COLLECT REQUEST HANDLERS - ₹1 Verification Flow
    // ===================================================================
    
    async function initiateUPICollect(e) {
        e.preventDefault();
        
        const upiId = document.getElementById('upiIdCollect')?.value || '';
        const statusDiv = document.getElementById('upiCollectStatus');
        const btn = e.target;
        
        if (!upiId) {
            if (statusDiv) {
                statusDiv.style.display = 'block';
                statusDiv.style.background = '#fee';
                statusDiv.style.color = '#c33';
                statusDiv.textContent = '⚠ Please enter UPI ID';
            }
            return;
        }
        
        btn.disabled = true;
        btn.textContent = 'Creating collect request...';
        if (statusDiv) {
            statusDiv.style.display = 'block';
            statusDiv.style.background = '#eef';
            statusDiv.style.color = '#333';
            statusDiv.textContent = '🔄 Creating ₹1 collect request...';
        }
        
        try {
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
            if (!csrfToken) throw new Error('CSRF token not found');
            
            const response = await fetch('/api/verify-upi-collect/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ upi_id: upiId })
            });
            
            const data = await response.json();
            console.log('UPI Collect Response:', data);
            
            if (data.status === 'success') {
                // Store order and payment IDs for later verification
                sessionStorage.setItem('upi_order_id', data.order_id);
                sessionStorage.setItem('upi_collect_initiated', 'true');
                
                if (statusDiv) {
                    statusDiv.style.background = '#eef';
                    statusDiv.style.color = '#333';
                    statusDiv.textContent = `📱 ${data.message}<br><strong>Check your UPI app - a ₹1 collect request was sent!</strong><br>Amount will be auto-refunded after verification.`;
                }
                
                btn.textContent = 'Waiting for payment...';
                document.getElementById('upiIdCollect').disabled = true;
                
                // Poll for payment status
                setTimeout(() => checkUPICollectStatus(data.order_id), 3000);
            } else {
                if (statusDiv) {
                    statusDiv.style.background = '#fee';
                    statusDiv.style.color = '#c33';
                    statusDiv.textContent = `❌ ${data.message || 'Failed to create collect request'}`;
                }
            }
        } catch (err) {
            console.error('UPI collect error:', err);
            if (statusDiv) {
                statusDiv.style.background = '#fee';
                statusDiv.style.color = '#c33';
                statusDiv.textContent = `❌ Error: ${err.message}`;
            }
        }
        
        btn.disabled = false;
    }
    
    async function checkUPICollectStatus(orderId) {
        // This would poll Razorpay for payment status
        // In production, implement webhook or polling logic
        console.log('Checking UPI payment status for order:', orderId);
    }
    
    // ===================================================================
    // REFUND PROCESSING HANDLERS
    // ===================================================================
    
    async function processRefund(e, orderId) {
        e.preventDefault();
        
        const reason = document.getElementById('refundReason')?.value || 'Refund requested';
        const amount = document.getElementById('refundAmount')?.value || null;
        const statusDiv = document.getElementById('refundStatus');
        const btn = e.target;
        
        btn.disabled = true;
        btn.textContent = 'Processing...';
        if (statusDiv) {
            statusDiv.style.display = 'block';
            statusDiv.style.background = '#eef';
            statusDiv.style.color = '#333';
            statusDiv.textContent = '🔄 Processing refund...';
        }
        
        try {
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
            if (!csrfToken) throw new Error('CSRF token not found');
            
            const response = await fetch('/api/refund/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({
                    order_id: orderId,
                    refund_amount: amount ? parseFloat(amount) : null,
                    reason: reason
                })
            });
            
            const data = await response.json();
            console.log('Refund Response:', data);
            
            if (data.status === 'success') {
                if (statusDiv) {
                    statusDiv.style.background = '#efe';
                    statusDiv.style.color = '#3c3';
                    statusDiv.textContent = `✅ Refund successful! ID: ${data.refund_id}`;
                }
                btn.textContent = '✓ Processed';
                btn.style.background = '#10b981';
            } else {
                if (statusDiv) {
                    statusDiv.style.background = '#fee';
                    statusDiv.style.color = '#c33';
                    statusDiv.textContent = `❌ ${data.message || 'Refund failed'}`;
                }
            }
        } catch (err) {
            console.error('Refund error:', err);
            if (statusDiv) {
                statusDiv.style.background = '#fee';
                statusDiv.style.color = '#c33';
                statusDiv.textContent = `❌ Error: ${err.message}`;
            }
        }
        
        btn.disabled = false;
    }
'''

# Find a good place to add the JavaScript (before closing body tag or in existing script section)
# Look for the last </script> tag or before </body>
if '</script>' in content:
    # Find the last script section
    last_script_idx = content.rfind('</script>')
    if last_script_idx != -1:
        # Insert before the last closing tag
        insertion_point = last_script_idx
        content = content[:insertion_point] + new_js_code + '\n    ' + content[insertion_point:]
else:
    # If no script section, add before closing body
    if '</body>' in content:
        closing_body_idx = content.rfind('</body>')
        script_wrapper = f'\n    <script>\n{new_js_code}\n    </script>\n    '
        content = content[:closing_body_idx] + script_wrapper + content[closing_body_idx:]

# Write the updated template back
with open(template_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Added JavaScript handlers to return_request.html:")
print("   - verifyBankAccount() - Bank verification with penny drop")
print("   - initiateUPICollect() - ₹1 collect request creation")
print("   - checkUPICollectStatus() - Poll for payment status")
print("   - processRefund() - Refund processing")
