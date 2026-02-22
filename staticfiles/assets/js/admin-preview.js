/* Admin Panel Preview Functions - Extracted from admin panel templates */

// Image preview function for add_banner.html
function previewImage(event) {
    const file = event.target.files[0];
    if (file) {
        const reader = new FileReader();
        reader.onload = function(e) {
            document.getElementById('preview-img').src = e.target.result;
            document.getElementById('image-preview').style.display = 'block';
        };
        reader.readAsDataURL(file);
    }
}

// Brand partner preview - from add_brand_partner.html
document.addEventListener('DOMContentLoaded', function() {
    // Logo preview on file change
    const logoInput = document.getElementById('logo');
    const previewLogo = document.getElementById('preview-logo');
    
    if (logoInput && previewLogo) {
        logoInput.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function(event) {
                    previewLogo.innerHTML = '<img src="' + event.target.result + '" alt="Preview" style="max-height: 80px; max-width: 150px; object-fit: contain; filter: grayscale(100%); opacity: 0.6;">';
                };
                reader.readAsDataURL(file);
            }
        });
    }
    
    // Name preview
    const nameInput = document.getElementById('name');
    const previewName = document.getElementById('preview-name');
    
    if (nameInput && previewName) {
        nameInput.addEventListener('input', function() {
            previewName.textContent = this.value || 'Brand Name';
        });
    }
});
