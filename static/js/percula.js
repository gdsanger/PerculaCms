/* PerculaCMS – Main JS */

(function () {
  'use strict';

  // ── Dark / Light Mode Toggle ──────────────────────────────────────────────
  const html      = document.documentElement;
  const btn       = document.getElementById('themeSwitcher');
  const icon      = document.getElementById('themeIcon');
  const STORAGE_KEY = 'percuia-theme';

  function applyTheme(theme) {
    html.setAttribute('data-bs-theme', theme);
    if (icon) {
      icon.className = theme === 'dark' ? 'bi bi-sun-fill' : 'bi bi-moon-stars-fill';
    }
    try { localStorage.setItem(STORAGE_KEY, theme); } catch (_) {}
  }

  function getPreferred() {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) return stored;
    } catch (_) {}
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  // Apply saved/preferred theme immediately (avoids flash)
  applyTheme(getPreferred());

  if (btn) {
    btn.addEventListener('click', function () {
      const current = html.getAttribute('data-bs-theme') || 'light';
      applyTheme(current === 'dark' ? 'light' : 'dark');
    });
  }

  // Listen for OS theme changes
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function (e) {
    try {
      if (!localStorage.getItem(STORAGE_KEY)) {
        applyTheme(e.matches ? 'dark' : 'light');
      }
    } catch (_) {
      applyTheme(e.matches ? 'dark' : 'light');
    }
  });

  // ── HTMX global config ────────────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', function () {
    if (typeof htmx !== 'undefined') {
      htmx.config.defaultSwapStyle = 'outerHTML';
    }

    // Auto-dismiss alerts after 5 s
    document.querySelectorAll('.alert.fade.show').forEach(function (el) {
      setTimeout(function () {
        var bsAlert = bootstrap.Alert.getOrCreateInstance(el);
        if (bsAlert) bsAlert.close();
      }, 5000);
    });
  });
})();
