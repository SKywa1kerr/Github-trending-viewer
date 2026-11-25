// Runs before first paint so the saved theme and accent never flash; app.js keeps them in sync afterwards.
(function () {
    var theme = 'dark', accent = 'indigo';
    try {
        theme = localStorage.getItem('theme') || theme;
        accent = localStorage.getItem('accent') || accent;
    } catch (error) { /* Storage may be disabled. */ }
    if (!/^(system|light|dark)$/.test(theme)) theme = 'dark';
    if (!/^(vermilion|indigo|teal|amber|rose)$/.test(accent)) accent = 'indigo';
    var dark = theme === 'dark' || (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
    var root = document.documentElement;
    root.dataset.theme = dark ? 'dark' : 'light';
    root.dataset.accent = accent;
    var metas = document.querySelectorAll('meta[name="theme-color"]');
    for (var i = 0; i < metas.length; i++) metas[i].content = dark ? '#000000' : '#f5f5f7';
})();
