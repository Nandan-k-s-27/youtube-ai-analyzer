/* ── global.js — Theme persistence across all pages ── */
(function () {
    var html = document.documentElement;

    // Apply saved theme IMMEDIATELY (before paint)
    var saved = localStorage.getItem('theme');
    if (saved) html.setAttribute('data-theme', saved);

    // Toggle handler — bind after DOM ready
    document.addEventListener('DOMContentLoaded', function () {
        var btn = document.getElementById('themeToggle');
        if (!btn) return;
        btn.addEventListener('click', function () {
            var current = html.getAttribute('data-theme');
            var next = current === 'dark' ? 'light' : 'dark';
            html.setAttribute('data-theme', next);
            localStorage.setItem('theme', next);
        });
    });
})();
