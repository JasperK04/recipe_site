(function () {
    try {
        const stored = localStorage.getItem('theme');
        const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
        const theme = stored || (prefersDark ? 'dark' : 'light');
        document.documentElement.classList.toggle('dark-mode', theme === 'dark');
        document.documentElement.classList.toggle('light-mode', theme === 'light');
    } catch (error) {
        // Device preference and CSS defaults remain available when storage is blocked.
    }
})();
