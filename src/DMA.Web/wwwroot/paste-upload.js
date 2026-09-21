function dmaExtensionFor(mimeType) {
    switch (mimeType) {
        case 'image/png': return 'png';
        case 'image/jpeg': return 'jpg';
        case 'image/webp': return 'webp';
        case 'image/gif': return 'gif';
        case 'image/bmp': return 'bmp';
        default: return 'png';
    }
}

window.dmaPasteUpload = {
    // Lets a container act like a Paint canvas: focus it (click) and Ctrl+V an
    // image straight from the clipboard. We hand the pasted image to the SAME
    // hidden <input type=file> that the existing "choose file" button uses, so
    // it goes through Blazor's normal (already working, full-resolution) upload
    // pipeline instead of a separate one.
    register: function (containerId) {
        var container = document.getElementById(containerId);
        if (!container || container.dataset.dmaPasteRegistered) return;
        container.dataset.dmaPasteRegistered = 'true';

        container.addEventListener('paste', function (e) {
            var items = (e.clipboardData || window.clipboardData).items;
            if (!items) return;

            for (var i = 0; i < items.length; i++) {
                if (items[i].type.indexOf('image') === -1) continue;

                var blob = items[i].getAsFile();
                if (!blob) continue;

                var fileName = 'pasted-' + Date.now() + '.' + dmaExtensionFor(blob.type);
                var file = new File([blob], fileName, { type: blob.type });

                var input = container.querySelector('input[type=file]');
                if (input) {
                    var dataTransfer = new DataTransfer();
                    dataTransfer.items.add(file);
                    input.files = dataTransfer.files;
                    input.dispatchEvent(new Event('change', { bubbles: true }));
                }

                e.preventDefault();
                break;
            }
        });
    }
};
