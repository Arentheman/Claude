function dmaApplyStoredTheme() {
    var theme = localStorage.getItem('dma-theme') || 'light';
    document.documentElement.setAttribute('data-bs-theme', theme);
}

window.dmaTheme = {
    get: function () {
        return localStorage.getItem('dma-theme') || 'light';
    },
    set: function (theme) {
        localStorage.setItem('dma-theme', theme);
        dmaApplyStoredTheme();
    }
};

// Blazor's enhanced navigation swaps page content without a full browser
// reload, so the inline no-FOUC <script> in App.razor's <head> only ever
// runs once (on the very first load). The <html data-bs-theme> attribute
// otherwise reverts to its default on every later in-app navigation
// because the server-rendered response never includes it. Re-apply the
// stored preference after each enhanced navigation to keep it in sync.
dmaApplyStoredTheme();
if (window.Blazor && typeof Blazor.addEventListener === 'function') {
    Blazor.addEventListener('enhancedload', dmaApplyStoredTheme);
}
