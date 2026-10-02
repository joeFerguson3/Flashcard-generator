/* Library: filter by subject, search and sort, all client-side. */
(function () {
  'use strict';
  var root = document.querySelector('[data-library-filters]');
  var grid = document.querySelector('[data-set-grid]');
  if (!root || !grid) return;
  var search = root.querySelector('[data-search]');
  var sort = root.querySelector('[data-sort]');
  var empty = document.querySelector('[data-no-results]');
  var chips = root.querySelectorAll('[data-subject]');
  var pressed = root.querySelector('[aria-pressed="true"]');
  var subject = pressed ? pressed.dataset.subject : '';

  try {
    var savedSort = localStorage.getItem('qn-library-sort');
    if (savedSort) sort.value = savedSort;
  } catch (e) {}

  function apply() {
    var q = search.value.trim().toLowerCase();
    var items = Array.prototype.slice.call(grid.children);
    var visible = 0;
    items.forEach(function (li) {
      var show = (!subject || li.dataset.subject === subject) &&
        (!q || li.dataset.title.indexOf(q) !== -1 || li.dataset.subject.toLowerCase().indexOf(q) !== -1);
      li.hidden = !show;
      if (show) visible++;
    });
    items.sort(function (a, b) {
      if (sort.value === 'az') return a.dataset.title.localeCompare(b.dataset.title);
      if (sort.value === 'score') return parseFloat(a.dataset.score) - parseFloat(b.dataset.score);
      return parseInt(b.dataset.updated, 10) - parseInt(a.dataset.updated, 10);
    }).forEach(function (li) { grid.appendChild(li); });
    empty.hidden = visible > 0;
  }

  chips.forEach(function (chip) {
    chip.addEventListener('click', function () {
      subject = chip.dataset.subject;
      chips.forEach(function (c) { c.setAttribute('aria-pressed', String(c === chip)); });
      var url = new URL(window.location.href);
      if (subject) url.searchParams.set('subject', subject); else url.searchParams.delete('subject');
      history.replaceState(null, '', url);
      apply();
    });
  });
  search.addEventListener('input', apply);
  sort.addEventListener('change', function () {
    try { localStorage.setItem('qn-library-sort', sort.value); } catch (e) {}
    apply();
  });
  apply();
})();
