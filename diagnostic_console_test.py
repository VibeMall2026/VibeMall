"""
Browser Console Test - Paste this code in your browser's DevTools Console
to debug the UPI field visibility issue
"""

# Paste the following JavaScript code in your browser's Developer Tools Console (F12):

test_code = """
// Test 1: Check if elements exist
console.log('=== TEST 1: Check if elements exist ===');
const upiBlock = document.getElementById('vmRpUpiBlockDesktop');
const upiInput = document.getElementById('vmRpUpiIdDesktop');
const upiBtn = document.getElementById('vmRpUpiVerifyBtnDesktop');
const bankBlock = document.getElementById('vmRpBankBlockDesktop');
const refundContainer = document.getElementById('vmRpRefundMethodsDesktop');

console.log('✓ UPI Block exists:', !!upiBlock);
console.log('✓ UPI Input exists:', !!upiInput);
console.log('✓ UPI Button exists:', !!upiBtn);
console.log('✓ Bank Block exists:', !!bankBlock);
console.log('✓ Refund Container exists:', !!refundContainer);

// Test 2: Check current display state
console.log('\\n=== TEST 2: Current CSS Display Property ===');
console.log('UPI Block display:', window.getComputedStyle(upiBlock).display);
console.log('Bank Block display:', window.getComputedStyle(bankBlock).display);
console.log('UPI Input display:', window.getComputedStyle(upiInput).display);

// Test 3: Find radio buttons
console.log('\\n=== TEST 3: Check Radio Buttons ===');
const radios = document.querySelectorAll('input[name="refund_method"]');
console.log('Total radios found:', radios.length);
radios.forEach((r, i) => {
    console.log(`Radio ${i}:`, {value: r.value, checked: r.checked, id: r.id});
});

// Test 4: Manually trigger UPI selection
console.log('\\n=== TEST 4: Manually Select UPI ===');
const upiRadio = Array.from(radios).find(r => r.value.toUpperCase() === 'UPI');
if (upiRadio) {
    console.log('UPI radio found, clicking...');
    upiRadio.checked = true;
    upiRadio.dispatchEvent(new Event('change', { bubbles: true }));
} else {
    console.warn('⚠️  UPI radio not found!');
}

// Test 5: Check toggle function
console.log('\\n=== TEST 5: Check toggleRefundFieldsDesktop Function ===');
console.log('Function exists:', typeof window.toggleRefundFieldsDesktop);

// Test 6: Manually set display property
console.log('\\n=== TEST 6: Force Show UPI Block ===');
if (upiBlock) {
    upiBlock.style.display = 'block';
    console.log('✓ UPI block forced to display:block');
    console.log('New display value:', window.getComputedStyle(upiBlock).display);
}

console.log('\\n=== END OF DIAGNOSTICS ===');
"""

print(test_code)
