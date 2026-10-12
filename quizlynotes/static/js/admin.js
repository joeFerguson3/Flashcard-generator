/* Stats console: tabs, sortable tables, filters and CSV download. */
(function () {
  'use strict';
  var root = document.querySelector('[data-stats]');
  if (!root) return;

  // ---- tabs (one section at a time; the URL hash remembers which) ----------
  var tabs = root.querySelectorAll('[data-tab]');
  var panels = root.querySelectorAll('[data-panel]');
  function showTab(id) {
    if (!root.querySelector('[data-panel="' + id + '"]')) id = 'overview';
    panels.forEach(function (p) { p.hidden = p.getAttribute('data-panel') !== id; });
    tabs.forEach(function (t) {
      if (t.getAttribute('data-tab') === id) t.setAttribute('aria-current', 'page'); else t.removeAttribute('aria-current');
    });
    root.querySelectorAll('[data-keep-hash]').forEach(function (a) {
      a.href = a.href.split('#')[0] + '#' + id;
    });
  }
  tabs.forEach(function (t) {
    t.addEventListener('click', function (e) {
      e.preventDefault();
      var id = t.getAttribute('data-tab');
      history.replaceState(null, '', '#' + id);
      showTab(id);
    });
  });
  showTab((location.hash || '#overview').slice(1));

  // ---- sortable tables -----------------------------------------------------
  function cellValue(td) {
    var raw = td.hasAttribute('data-sort') ? td.getAttribute('data-sort') : td.textContent.trim();
    if (raw === '' || raw === '–') return { empty: true };
    var num = parseFloat(raw.replace(/[,%s]/g, ''));
    if (!isNaN(num) && /^-?[\d.,]+\s*[%s]?/.test(raw) && !/^\d{4}-\d{2}-\d{2}/.test(raw)) return { num: num };
    return { str: raw.toLowerCase() };
  }
  root.querySelectorAll('table[data-sortable]').forEach(function (table) {
    var heads = table.querySelectorAll('thead th');
    heads.forEach(function (th, col) {
      th.classList.add('is-sortable');
      th.setAttribute('tabindex', '0');
      th.setAttribute('role', 'button');
      function sort() {
        var dir = th.getAttribute('aria-sort') === 'descending' ? 'ascending' : 'descending';
        heads.forEach(function (h) { h.removeAttribute('aria-sort'); });
        th.setAttribute('aria-sort', dir);
        var body = table.tBodies[0];
        var rows = Array.prototype.slice.call(body.rows).filter(function (r) { return r.cells.length > 1; });
        rows.sort(function (a, b) {
          var x = cellValue(a.cells[col]), y = cellValue(b.cells[col]);
          if (x.empty || y.empty) return x.empty && y.empty ? 0 : x.empty ? 1 : -1;  // blanks last
          var r = x.num !== undefined && y.num !== undefined ? x.num - y.num : String(x.str || x.num).localeCompare(String(y.str || y.num));
          return dir === 'ascending' ? r : -r;
        });
        rows.forEach(function (r) { body.appendChild(r); });
      }
      th.addEventListener('click', sort);
      th.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); sort(); } });
    });
  });

  // ---- filters ---------------------------------------------------------------
  root.querySelectorAll('[data-table-filter]').forEach(function (input) {
    var table = document.getElementById(input.getAttribute('data-table-filter'));
    if (!table) return;
    input.addEventListener('input', function () {
      var q = input.value.trim().toLowerCase();
      Array.prototype.forEach.call(table.tBodies[0].rows, function (r) {
        r.hidden = q && r.textContent.toLowerCase().indexOf(q) === -1;
      });
    });
  });

  // ---- CSV download (visible rows, current order) ------------------------------
  root.querySelectorAll('[data-csv]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var table = document.getElementById(btn.getAttribute('data-csv'));
      if (!table) return;
      var lines = [];
      Array.prototype.forEach.call(table.rows, function (r) {
        if (r.hidden) return;
        lines.push(Array.prototype.map.call(r.cells, function (c) {
          var v = c.innerText.replace(/\s+/g, ' ').trim();
          return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v;
        }).join(','));
      });
      var blob = new Blob([lines.join('\n')], { type: 'text/csv' });
      var a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = 'quizlynotes-' + btn.getAttribute('data-csv').replace(/^t-/, '') + '.csv';
      document.body.appendChild(a); a.click(); a.remove();
    });
  });
})();
