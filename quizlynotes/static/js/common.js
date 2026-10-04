/* Shared helpers: API calls with CSRF, theme, toasts, tabs, loaders. */
(function () {
  'use strict';

  var csrf = (document.querySelector('meta[name="csrf-token"]') || {}).content || '';

  function request(url, options) {
    options = options || {};
    var headers = Object.assign({ 'X-CSRFToken': csrf, 'Accept': 'application/json' }, options.headers || {});
    var body = options.body;
    if (body && !(body instanceof FormData) && typeof body !== 'string') {
      headers['Content-Type'] = 'application/json';
      body = JSON.stringify(body);
    }
    return fetch(url, { method: options.method || 'POST', headers: headers, body: body, credentials: 'same-origin' })
      .then(function (res) {
        return res.json().catch(function () { return {}; }).then(function (data) {
          if (!res.ok) {
            var msg = data.error || (res.status === 413 ? 'That file is too large.' : 'Something went wrong. Please try again.');
            var err = new Error(msg);
            err.status = res.status;
            if (res.status === 402 && data.upgrade) {
              err.upgrade = true;
              showUpgrade(msg, data.upgrade_url);
            }
            throw err;
          }
          return data;
        });
      }, function () {
        throw new Error('Connection problem. Check your internet and try again.');
      });
  }

  function showUpgrade(message, url) {
    var dlg = document.querySelector('[data-upgrade-modal]');
    if (!dlg || typeof dlg.showModal !== 'function') {
      if (url) window.location.href = url;
      return;
    }
    dlg.querySelector('[data-upgrade-message]').textContent = message;
    if (url) dlg.querySelector('[data-upgrade-link]').setAttribute('href', url);
    if (!dlg.open) dlg.showModal();
  }

  function toast(message, kind) {
    var host = document.querySelector('.toasts');
    if (!host) {
      host = document.createElement('div');
      host.className = 'toasts';
      host.setAttribute('role', 'status');
      host.setAttribute('aria-live', 'polite');
      document.body.appendChild(host);
    }
    var el = document.createElement('div');
    el.className = 'toast' + (kind ? ' toast--' + kind : '');
    el.textContent = message;
    host.appendChild(el);
    setTimeout(function () { el.remove(); }, 5000);
  }

  // Rotating messages while the AI works, so long waits feel alive.
  var LOADER_MESSAGES = [
    'Reading your notes…', 'Finding the key ideas…', 'Organising topics…',
    'Writing questions…', 'Checking answers…', 'Almost there…'
  ];
  function startLoader(container, messages) {
    messages = messages || LOADER_MESSAGES;
    var el = container.querySelector('[data-loader-msg]');
    var i = 0;
    if (el) el.textContent = messages[0];
    var timer = setInterval(function () {
      i = Math.min(i + 1, messages.length - 1);
      if (el) el.textContent = messages[i];
    }, 7000);
    return function stop() { clearInterval(timer); };
  }

  function tabs(root, onChange) {
    var buttons = root.querySelectorAll('[role="tab"]');
    buttons.forEach(function (btn) {
      btn.addEventListener('click', function () {
        buttons.forEach(function (b) { b.setAttribute('aria-selected', String(b === btn)); });
        root.querySelectorAll('[data-panel]').forEach(function (p) {
          p.hidden = p.getAttribute('data-panel') !== btn.getAttribute('data-tab');
        });
        if (onChange) onChange(btn.getAttribute('data-tab'));
      });
    });
  }

  // Theme: "system" (no attribute), "light" or "dark".
  function currentTheme() {
    try { return localStorage.getItem('qn-theme') || 'system'; } catch (e) { return 'system'; }
  }
  function setTheme(theme) {
    try {
      if (theme === 'system') localStorage.removeItem('qn-theme'); else localStorage.setItem('qn-theme', theme);
    } catch (e) {}
    if (theme === 'system') document.documentElement.removeAttribute('data-theme');
    else document.documentElement.setAttribute('data-theme', theme);
    syncThemeUI();
  }
  function syncThemeUI() {
    var t = currentTheme();
    var label = { system: 'System', light: 'Light', dark: 'Dark' }[t];
    document.querySelectorAll('[data-theme-label]').forEach(function (el) { el.textContent = label; });
    document.querySelectorAll('[data-theme-choice] input').forEach(function (input) { input.checked = input.value === t; });
  }

  document.addEventListener('DOMContentLoaded', function () {
    syncThemeUI();
    document.querySelectorAll('[data-theme-cycle]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var order = ['system', 'light', 'dark'];
        setTheme(order[(order.indexOf(currentTheme()) + 1) % order.length]);
      });
    });
    document.querySelectorAll('[data-theme-choice] input').forEach(function (input) {
      input.addEventListener('change', function () { setTheme(input.value); });
    });

    document.querySelectorAll('[data-dismiss]').forEach(function (btn) {
      btn.addEventListener('click', function () { btn.parentElement.remove(); });
    });
    setTimeout(function () {
      document.querySelectorAll('.toast:not(.toast--error)').forEach(function (t) { t.remove(); });
    }, 6000);

    // Copy-to-clipboard buttons (share and invite links).
    document.querySelectorAll('[data-copy]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var input = btn.parentElement.querySelector('[data-copy-source]');
        if (!input) return;
        var done = function () {
          var label = btn.textContent;
          btn.textContent = 'Copied!';
          setTimeout(function () { btn.textContent = label; }, 1800);
        };
        if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(input.value).then(done, function () { input.select(); });
        else { input.select(); try { document.execCommand('copy'); done(); } catch (e) {} }
      });
    });

    document.querySelectorAll('form[data-confirm]').forEach(function (form) {
      form.addEventListener('submit', function (e) {
        if (!window.confirm(form.getAttribute('data-confirm'))) e.preventDefault();
      });
    });

    // Close the account menu when clicking elsewhere.
    document.addEventListener('click', function (e) {
      document.querySelectorAll('details.menu[open], details.gen-options[open]').forEach(function (d) {
        if (!d.contains(e.target)) d.removeAttribute('open');
      });
    });

    var header = document.querySelector('.site-header:not(.site-header--app)');
    if (header) {
      var onScroll = function () { header.classList.toggle('is-scrolled', window.scrollY > 8); };
      onScroll();
      window.addEventListener('scroll', onScroll, { passive: true });
    }
  });

  window.QN = { request: request, toast: toast, startLoader: startLoader, tabs: tabs, showUpgrade: showUpgrade };
})();
