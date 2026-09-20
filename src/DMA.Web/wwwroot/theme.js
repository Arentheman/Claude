window.dmaTheme = {
    get: function () {
        return localStorage.getItem('dma-theme') || 'light';
    },
    set: function (theme) {
        localStorage.setItem('dma-theme', theme);
        document.documentElement.setAttribute('data-bs-theme', theme);
    }
};
