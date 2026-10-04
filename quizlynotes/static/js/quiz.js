/* Quiz player.
 *
 * Renders entirely from the JSON in #quiz-data: for each topic, the notes,
 * then its questions. One step on screen at a time, keyboard friendly,
 * every answer explained. All text is inserted with textContent.
 */
(function () {
  'use strict';
  var dataEl = document.getElementById('quiz-data');
  var root = document.getElementById('player');
  if (!dataEl || !root) return;
  var data = JSON.parse(dataEl.textContent);

  var KIND_LABEL = {
    multiple_choice: 'Multiple choice', true_false: 'True or false', fill_blank: 'Fill in the blank',
    short_answer: 'Short answer', ordering: 'Put in order', matching: 'Match up',
    multi_select: 'Select all that apply', categorize: 'Sort into groups', numeric: 'Numeric answer',
    explain: 'Explain'
  };

  // ---- helpers -----------------------------------------------------------
  function h(tag, attrs, children) {
    var node = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      var v = attrs[k];
      if (v === null || v === undefined || v === false) return;
      if (k === 'text') node.textContent = v;
      else if (k === 'class') node.className = v;
      else if (k.slice(0, 2) === 'on') node.addEventListener(k.slice(2), v);
      else node.setAttribute(k, v === true ? '' : v);
    });
    (children || []).forEach(function (c) {
      if (c === null || c === undefined || c === false) return;
      node.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    });
    return node;
  }
  function shuffle(list) {
    var a = list.slice();
    for (var i = a.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var t = a[i]; a[i] = a[j]; a[j] = t;
    }
    return a;
  }
  function normalise(s) {
    return String(s || '').toLowerCase()
      .normalize('NFKD').replace(/[̀-ͯ]/g, '')
      .replace(/[^\p{L}\p{N}\s.]/gu, ' ')
      .replace(/\b(the|a|an)\b/g, ' ')
      .replace(/\s+/g, ' ').trim();
  }
  function levenshtein(a, b) {
    if (a === b) return 0;
    var prev = [], cur = [], i, j;
    for (j = 0; j <= b.length; j++) prev[j] = j;
    for (i = 1; i <= a.length; i++) {
      cur = [i];
      for (j = 1; j <= b.length; j++) {
        cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
      }
      prev = cur;
    }
    return prev[b.length];
  }
  /* Forgiving match: ignores case, punctuation, articles, plural "s" and
     small typos, but numbers must be exact. */
  function matches(given, expected) {
    var g = normalise(given), e = normalise(expected);
    if (!g || !e) return false;
    if (g === e) return true;
    var digits = function (s) { return (s.match(/\d+(\.\d+)?/g) || []).join(','); };
    if (digits(e) && digits(g) !== digits(e)) return false;
    var strip = function (s) { return s.replace(/(es|s)\b/g, ''); };
    if (strip(g) === strip(e)) return true;
    var allowed = e.length <= 4 ? 0 : e.length <= 8 ? 1 : Math.floor(e.length * 0.2);
    return levenshtein(g, e) <= allowed;
  }

  // ---- build steps -------------------------------------------------------
  var steps = [];
  var questions = [];
  (data.groups || []).forEach(function (group) {
    if (group.notes && group.notes.length) steps.push({ type: 'notes', group: group });
    group.cards.forEach(function (card) {
      var q = { type: 'question', card: card, topic: group.heading, result: null };
      steps.push(q);
      questions.push(q);
    });
  });
  if (!questions.length) {
    root.appendChild(h('div', { class: 'step' }, [h('p', { text: 'No questions to show.' })]));
    return;
  }
  var index = 0;
  var progressFill, progressLabel;

  var startedAt = Date.now();
  function formatTime(ms) {
    var sec = Math.floor(ms / 1000);
    return Math.floor(sec / 60) + ':' + ('0' + (sec % 60)).slice(-2);
  }

  function renderProgress() {
    var done = questions.filter(function (q) { return q.result !== null; }).length;
    progressFill.style.width = (done / questions.length * 100) + '%';
    progressLabel.textContent = done + ' / ' + questions.length;
  }

  function show(i) {
    index = i;
    var stage = root.querySelector('[data-stage]');
    stage.innerHTML = '';
    var step = steps[i];
    var node = step ? (step.type === 'notes' ? renderNotes(step) : renderQuestion(step)) : renderResults();
    stage.appendChild(node);
    renderProgress();
    var focusTarget = node.querySelector('[data-autofocus]');
    if (focusTarget) focusTarget.focus({ preventScroll: true });
    var top = root.getBoundingClientRect().top + window.scrollY - 90;
    if (window.scrollY > top) window.scrollTo({ top: top, behavior: 'smooth' });
  }
  function next() { show(index + 1); }

  // ---- notes step --------------------------------------------------------
  /* Notes are shown in bite-sized pages. Each level-1 point leads a "chunk";
     its details sit underneath as separate, spaced items. Long topics are
     split into several short pages the student steps through. */
  var POINTS_PER_PAGE = 6;

  function chunksOf(points) {
    var chunks = [];
    (points || []).forEach(function (p) {
      var level = p.level || 1;
      if (level === 1 || !chunks.length) chunks.push({ lead: level === 1 ? p : null, items: [] });
      var chunk = chunks[chunks.length - 1];
      if (level === 1) return;
      if (level === 2 || !chunk.items.length) chunk.items.push({ point: p, subs: [] });
      else chunk.items[chunk.items.length - 1].subs.push(p);
    });
    return chunks;
  }
  function chunkSize(c) {
    return (c.lead ? 1 : 0) + c.items.reduce(function (n, it) { return n + 1 + it.subs.length; }, 0);
  }
  function notePages(group) {
    var pages = [];
    group.notes.forEach(function (n) {
      var title = n.subheading && n.subheading !== group.heading ? n.subheading : '';
      var current = null;
      chunksOf(n.points).forEach(function (chunk) {
        // Split very long chunks so no page is a wall of text.
        var parts = [];
        if (chunkSize(chunk) > POINTS_PER_PAGE) {
          for (var i = 0; i < chunk.items.length; i += POINTS_PER_PAGE - 1) {
            parts.push({ lead: chunk.lead, items: chunk.items.slice(i, i + POINTS_PER_PAGE - 1), cont: i > 0 });
          }
        } else parts.push(chunk);
        parts.forEach(function (part) {
          if (!current || current.size + chunkSize(part) > POINTS_PER_PAGE) {
            current = { title: title, chunks: [], size: 0 };
            pages.push(current);
          }
          current.chunks.push(part);
          current.size += chunkSize(part);
        });
      });
    });
    return pages.length ? pages : [{ title: '', chunks: [], size: 0 }];
  }
  // "Term: explanation" -> bold term, so key words stand out when skimming.
  function pointText(text) {
    var i = text.indexOf(': ');
    if (i > 0 && i < 48) return [h('strong', { text: text.slice(0, i) }), document.createTextNode(text.slice(i))];
    return [document.createTextNode(text)];
  }

  function renderNotes(step) {
    var pages = notePages(step.group);
    var page = 0;
    var article = h('article', { class: 'step step--notes' });
    var count = step.group.cards.length;

    function draw() {
      article.innerHTML = '';
      var pg = pages[page];
      article.appendChild(h('p', { class: 'step__kind' }, [
        'Read first',
        pages.length > 1 ? h('span', { class: 'step__topic', text: ' · Part ' + (page + 1) + ' of ' + pages.length }) : null
      ]));
      article.appendChild(h('h2', { class: 'notes-title', text: step.group.heading }));
      if (pg.title && (page === 0 || pages[page - 1].title !== pg.title)) article.appendChild(h('h3', { class: 'notes-sub', text: pg.title }));
      else if (pg.title) article.appendChild(h('h3', { class: 'notes-sub notes-sub--cont', text: pg.title + ' (continued)' }));

      var body = h('div', { class: 'chunks' });
      pg.chunks.forEach(function (c) {
        var chunk = h('section', { class: 'chunk' });
        if (c.lead) chunk.appendChild(h('p', { class: 'chunk__lead' }, pointText(c.lead.text).concat(c.cont ? [h('span', { class: 'muted', text: ' (cont.)' })] : [])));
        if (c.items.length) {
          chunk.appendChild(h('ul', { class: 'chunk__items' }, c.items.map(function (it) {
            return h('li', { class: 'chunk__item' }, [
              h('p', null, pointText(it.point.text)),
              it.subs.length ? h('ul', { class: 'chunk__subs' }, it.subs.map(function (sp) { return h('li', null, pointText(sp.text)); })) : null
            ]);
          })));
        }
        body.appendChild(chunk);
      });
      article.appendChild(body);

      var last = page === pages.length - 1;
      var dots = pages.length > 1 ? h('div', { class: 'page-dots', 'aria-hidden': 'true' }, pages.map(function (_, i) {
        return h('span', { class: i === page ? 'is-on' : '' });
      })) : h('span', { class: 'step__hint', text: count + ' question' + (count === 1 ? '' : 's') + ' on this topic' });
      var back = page > 0 ? h('button', { class: 'btn btn--ghost', type: 'button', text: '← Back', onclick: function () { page--; draw(); } }) : null;
      var fwd = h('button', {
        class: 'btn btn--primary', type: 'button', 'data-autofocus': true,
        text: last ? 'I’m ready →' : 'Next →',
        onclick: function () { if (last) next(); else { page++; draw(); } }
      });
      article.appendChild(h('div', { class: 'step__actions' }, [dots, h('div', { class: 'btn-row' }, [back, fwd])]));
      fwd.focus({ preventScroll: true });
    }
    article._keyHandler = function (key) {
      if (key === 'ArrowRight' && page < pages.length - 1) { page++; draw(); }
      else if (key === 'ArrowLeft' && page > 0) { page--; draw(); }
    };
    draw();
    return article;
  }

  // ---- question steps ----------------------------------------------------
  function renderQuestion(step) {
    var card = step.card;
    var article = h('article', { class: 'step', 'aria-live': 'polite' });
    article.appendChild(h('p', { class: 'step__kind' }, [
      KIND_LABEL[card.kind] || 'Question',
      h('span', { class: 'step__topic', text: ' · ' + step.topic })
    ]));
    var actions = h('div', { class: 'step__actions' });
    var continueBtn = h('button', { class: 'btn btn--primary', type: 'button', text: index === steps.length - 1 ? 'See results' : 'Continue →', onclick: next });

    function finish(correct, answerText, allowOverride) {
      step.result = correct;
      renderProgress();
      var fb = h('div', { class: 'feedback ' + (correct ? 'feedback--good' : 'feedback--bad') }, [
        h('p', { class: 'feedback__title', text: correct ? 'Correct' : 'Not quite' }),
        !correct && answerText ? h('p', { class: 'feedback__answer' }, ['Answer: ', h('strong', { text: answerText })]) : null,
        card.explanation ? h('p', { text: card.explanation }) : null
      ]);
      if (!correct && allowOverride) {
        var override = h('button', { type: 'button', class: 'link-btn small', text: 'I was right, count it', onclick: function () {
          step.result = true;
          fb.className = 'feedback feedback--good';
          fb.querySelector('.feedback__title').textContent = 'Counted as correct';
          override.remove();
          renderProgress();
        } });
        fb.appendChild(h('p', { class: 'feedback__override' }, [override]));
      }
      article.insertBefore(fb, actions);
      actions.innerHTML = '';
      actions.appendChild(h('span', { class: 'step__hint', text: 'Press Enter to continue' }));
      actions.appendChild(continueBtn);
      continueBtn.focus({ preventScroll: true });
    }

    var renderers = {
      multiple_choice: mcq, true_false: tf, fill_blank: blanks, short_answer: shortAnswer, ordering: ordering,
      matching: matchUp, multi_select: multiSelect, categorize: categorize, numeric: numeric, explain: explain
    };
    (renderers[card.kind] || shortAnswer)(card, article, actions, finish);
    article.appendChild(actions);
    return article;
  }

  function choiceList(card, article, options, correctValue, finish, extraClass) {
    var list = h('div', { class: 'options' + (extraClass ? ' ' + extraClass : ''), role: 'group' });
    var buttons = options.map(function (opt, i) {
      var key = extraClass ? opt.key : String.fromCharCode(65 + i);
      var btn = h('button', { type: 'button', class: 'opt', 'data-value': opt.value, 'data-autofocus': i === 0 ? true : null }, [
        h('span', { class: 'opt__key', text: key }), h('span', { text: opt.label })
      ]);
      btn.addEventListener('click', function () { choose(btn); });
      return btn;
    });
    function choose(btn) {
      var correct = btn.getAttribute('data-value') === correctValue;
      buttons.forEach(function (b) {
        b.disabled = true;
        if (b.getAttribute('data-value') === correctValue) b.classList.add('is-correct');
        else if (b === btn) b.classList.add('is-wrong');
        else b.classList.add('is-dim');
      });
      finish(correct, null);
    }
    buttons.forEach(function (b) { list.appendChild(b); });
    list._keys = function (key) {
      var i = options.findIndex(function (o, n) {
        var k = extraClass ? o.key : String.fromCharCode(65 + n);
        return k.toLowerCase() === key.toLowerCase() || String(n + 1) === key;
      });
      if (i >= 0 && !buttons[i].disabled) choose(buttons[i]);
    };
    article._keyHandler = list._keys;
    return list;
  }

  function mcq(card, article, actions, finish) {
    article.appendChild(h('h2', { class: 'step__q', text: card.prompt }));
    var opts = shuffle(card.options).map(function (o) { return { value: o, label: o }; });
    article.appendChild(choiceList(card, article, opts, card.answers[0], finish));
    actions.appendChild(h('span', { class: 'step__hint', text: 'Tip: press A–' + String.fromCharCode(64 + opts.length) }));
  }

  function tf(card, article, actions, finish) {
    article.appendChild(h('h2', { class: 'step__q', text: card.prompt }));
    var opts = [{ value: 'true', label: 'True', key: 'T' }, { value: 'false', label: 'False', key: 'F' }];
    article.appendChild(choiceList(card, article, opts, card.answers[0], finish, 'tf'));
    actions.appendChild(h('span', { class: 'step__hint', text: 'Tip: press T or F' }));
  }

  function blanks(card, article, actions, finish) {
    var parts = card.prompt.split('{blank}');
    var inputs = [];
    var sentence = h('p', { class: 'blank-sentence' });
    parts.forEach(function (part, i) {
      sentence.appendChild(document.createTextNode(part));
      if (i < parts.length - 1) {
        var input = h('input', { class: 'blank-input', type: 'text', autocomplete: 'off', autocapitalize: 'off', spellcheck: 'false', 'aria-label': 'Blank ' + (i + 1), 'data-autofocus': i === 0 ? true : null });
        input.style.width = Math.max(6, Math.min(18, (card.answers[i] || '').length + 2)) + 'ch';
        inputs.push(input);
        sentence.appendChild(input);
      }
    });
    article.appendChild(sentence);
    var check = h('button', { type: 'button', class: 'btn btn--primary', text: 'Check' });
    var giveUp = h('button', { type: 'button', class: 'link-btn small', text: 'Show answer' });
    function grade(reveal) {
      var all = true;
      inputs.forEach(function (input, i) {
        var ok = !reveal && matches(input.value, card.answers[i]);
        all = all && ok;
        input.classList.add(ok ? 'is-correct' : 'is-wrong');
        if (!ok) input.value = input.value ? input.value + ' → ' + card.answers[i] : card.answers[i];
        input.readOnly = true;
        input.style.width = Math.max(6, Math.min(40, input.value.length + 2)) + 'ch';
      });
      finish(all, null, !reveal && !all);
    }
    check.addEventListener('click', function () { grade(false); });
    giveUp.addEventListener('click', function () { grade(true); });
    inputs.forEach(function (input, i) {
      input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
          e.preventDefault();
          e.stopPropagation();
          if (i < inputs.length - 1 && !inputs[i + 1].value) inputs[i + 1].focus(); else grade(false);
        }
      });
    });
    actions.appendChild(giveUp);
    actions.appendChild(check);
  }

  function shortAnswer(card, article, actions, finish) {
    article.appendChild(h('h2', { class: 'step__q', text: card.prompt }));
    var input = h('input', { class: 'answer-input', type: 'text', autocomplete: 'off', placeholder: 'Type your answer', 'aria-label': 'Your answer', 'data-autofocus': true });
    article.appendChild(input);
    var check = h('button', { type: 'button', class: 'btn btn--primary', text: 'Check' });
    var giveUp = h('button', { type: 'button', class: 'link-btn small', text: 'Show answer' });
    function grade(reveal) {
      var ok = !reveal && (card.answers || []).some(function (a) { return matches(input.value, a); });
      input.readOnly = true;
      input.classList.add(ok ? 'is-correct' : 'is-wrong');
      finish(ok, card.answers[0], !reveal && !ok && input.value.trim().length > 0);
    }
    check.addEventListener('click', function () { if (input.value.trim()) grade(false); else input.focus(); });
    giveUp.addEventListener('click', function () { grade(true); });
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && input.value.trim()) { e.preventDefault(); e.stopPropagation(); grade(false); }
    });
    actions.appendChild(giveUp);
    actions.appendChild(check);
  }

  function ordering(card, article, actions, finish) {
    article.appendChild(h('h2', { class: 'step__q', text: card.prompt }));
    var correct = card.options;
    var order = shuffle(correct);
    if (order.join('\u0000') === correct.join('\u0000') && correct.length > 1) order.push(order.shift());
    var list = h('ol', { class: 'order-list' });
    var locked = false;

    function draw() {
      list.innerHTML = '';
      order.forEach(function (text, i) {
        var up = h('button', { type: 'button', 'aria-label': 'Move up', disabled: locked || i === 0 }, [arrow('up')]);
        var down = h('button', { type: 'button', 'aria-label': 'Move down', disabled: locked || i === order.length - 1 }, [arrow('down')]);
        up.addEventListener('click', function () { move(i, i - 1, true); });
        down.addEventListener('click', function () { move(i, i + 1, true); });
        var li = h('li', { class: 'order-item', 'data-i': i }, [
          h('span', { class: 'order-item__n', text: String(i + 1) }),
          h('span', { class: 'order-item__text', text: text }),
          h('span', { class: 'order-item__btns' }, [up, down])
        ]);
        if (!locked) enableDrag(li, i);
        list.appendChild(li);
      });
    }
    function move(from, to, refocus) {
      if (to < 0 || to >= order.length) return;
      var item = order.splice(from, 1)[0];
      order.splice(to, 0, item);
      draw();
      if (refocus) {
        var btns = list.children[to].querySelectorAll('button');
        (to < from ? btns[0] : btns[1]).focus();
        if (document.activeElement && document.activeElement.disabled) btns[to < from ? 1 : 0].focus();
      }
    }
    // Pointer-based dragging: works with mouse, touch and pen.
    function enableDrag(li, i) {
      li.addEventListener('pointerdown', function (e) {
        if (e.target.closest('button')) return;
        e.preventDefault();
        li.setPointerCapture(e.pointerId);
        li.classList.add('is-dragging');
        var from = i;
        function onMove(ev) {
          var items = Array.prototype.slice.call(list.children);
          var target = items.findIndex(function (other) {
            var r = other.getBoundingClientRect();
            return ev.clientY >= r.top && ev.clientY <= r.bottom;
          });
          if (target >= 0 && target !== from) {
            var item = order.splice(from, 1)[0];
            order.splice(target, 0, item);
            var moving = items[from];
            if (target > from) list.insertBefore(moving, items[target].nextSibling); else list.insertBefore(moving, items[target]);
            from = target;
          }
        }
        function onUp() {
          li.removeEventListener('pointermove', onMove);
          li.removeEventListener('pointerup', onUp);
          li.removeEventListener('pointercancel', onUp);
          draw();
        }
        li.addEventListener('pointermove', onMove);
        li.addEventListener('pointerup', onUp);
        li.addEventListener('pointercancel', onUp);
      });
    }
    function arrow(dir) {
      var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.setAttribute('width', '14'); svg.setAttribute('height', '14'); svg.setAttribute('viewBox', '0 0 14 14');
      var p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      p.setAttribute('d', dir === 'up' ? 'M3 9l4-4 4 4' : 'M3 5l4 4 4-4');
      p.setAttribute('fill', 'none'); p.setAttribute('stroke', 'currentColor'); p.setAttribute('stroke-width', '1.8');
      svg.appendChild(p);
      return svg;
    }
    draw();
    article.appendChild(h('p', { class: 'step__hint', text: 'Drag items, or use the arrows.' }));
    article.appendChild(list);
    var check = h('button', { type: 'button', class: 'btn btn--primary', text: 'Check order', 'data-autofocus': true });
    check.addEventListener('click', function () {
      locked = true;
      draw();
      var allOk = true;
      Array.prototype.forEach.call(list.children, function (li, i) {
        var ok = order[i] === correct[i];
        allOk = allOk && ok;
        li.classList.add(ok ? 'is-correct' : 'is-wrong');
        if (!ok) li.querySelector('.order-item__btns').replaceWith(h('span', { class: 'order-item__fix', text: 'should be ' + (correct.indexOf(order[i]) + 1) }));
        else li.querySelector('.order-item__btns').remove();
      });
      finish(allOk, allOk ? null : correct.join(' → '));
    });
    actions.appendChild(check);
  }

  // Match up: choose the right definition for each term from a dropdown.
  function matchUp(card, article, actions, finish) {
    article.appendChild(h('h2', { class: 'step__q', text: card.prompt }));
    var choices = shuffle(card.answers);
    var selects = [];
    var rows = card.options.map(function (term, i) {
      var select = h('select', { class: 'match-select', 'aria-label': 'Match for ' + term, 'data-autofocus': i === 0 ? true : null },
        [h('option', { value: '', text: 'Choose…' })].concat(choices.map(function (c) { return h('option', { value: c, text: c }); })));
      selects.push(select);
      select.addEventListener('change', update);
      return h('div', { class: 'match-row' }, [h('span', { class: 'match-row__term', text: term }), select]);
    });
    article.appendChild(h('div', { class: 'match-rows' }, rows));
    var check = h('button', { type: 'button', class: 'btn btn--primary', text: 'Check', disabled: true });
    function update() {
      // Each definition can only be used once: grey it out in the other dropdowns.
      var used = selects.map(function (s) { return s.value; });
      selects.forEach(function (s) {
        Array.prototype.forEach.call(s.options, function (o) {
          o.disabled = !!o.value && o.value !== s.value && used.indexOf(o.value) !== -1;
        });
      });
      check.disabled = used.some(function (v) { return !v; });
    }
    check.addEventListener('click', function () {
      var all = true;
      selects.forEach(function (sel, i) {
        var ok = sel.value === card.answers[i];
        all = all && ok;
        sel.disabled = true;
        sel.parentNode.classList.add(ok ? 'is-correct' : 'is-wrong');
        if (!ok) sel.parentNode.appendChild(h('span', { class: 'match-row__fix', text: '→ ' + card.answers[i] }));
      });
      finish(all, null);
    });
    actions.appendChild(h('span', { class: 'step__hint', text: 'Pick a match for every term' }));
    actions.appendChild(check);
  }

  // Select all that apply: toggle options, then check.
  function multiSelect(card, article, actions, finish) {
    article.appendChild(h('h2', { class: 'step__q', text: card.prompt }));
    var opts = shuffle(card.options);
    var buttons = opts.map(function (o, i) {
      var b = h('button', { type: 'button', class: 'opt opt--check', 'aria-pressed': 'false', 'data-value': o, 'data-autofocus': i === 0 ? true : null },
        [h('span', { class: 'opt__key opt__box', 'aria-hidden': 'true' }), h('span', { text: o })]);
      b.addEventListener('click', function () { b.setAttribute('aria-pressed', String(b.getAttribute('aria-pressed') !== 'true')); });
      return b;
    });
    article.appendChild(h('div', { class: 'options', role: 'group' }, buttons));
    var check = h('button', { type: 'button', class: 'btn btn--primary', text: 'Check' });
    check.addEventListener('click', function () {
      var all = true;
      buttons.forEach(function (b) {
        var picked = b.getAttribute('aria-pressed') === 'true';
        var right = card.answers.indexOf(b.getAttribute('data-value')) !== -1;
        b.disabled = true;
        if (right && picked) b.classList.add('is-correct');
        else if (right && !picked) { b.classList.add('is-missed'); all = false; }
        else if (!right && picked) { b.classList.add('is-wrong'); all = false; }
        else b.classList.add('is-dim');
      });
      finish(all, all ? null : card.answers.join(', '));
    });
    actions.appendChild(h('span', { class: 'step__hint', text: card.answers.length > 1 ? 'More than one answer is correct' : '' }));
    actions.appendChild(check);
  }

  // Sort into groups: pick a category for each item.
  function categorize(card, article, actions, finish) {
    article.appendChild(h('h2', { class: 'step__q', text: card.prompt }));
    var cats = [];
    card.answers.forEach(function (a) { if (cats.indexOf(a) === -1) cats.push(a); });
    var order = shuffle(card.options.map(function (o, i) { return i; }));
    var picks = {};
    var check = h('button', { type: 'button', class: 'btn btn--primary', text: 'Check', disabled: true });
    var rows = order.map(function (idx, n) {
      var group = h('div', { class: 'segmented segmented--cats', role: 'radiogroup', 'aria-label': card.options[idx] });
      cats.forEach(function (c) {
        var btn = h('button', { type: 'button', class: 'cat-btn', 'aria-pressed': 'false', text: c, 'data-autofocus': n === 0 && c === cats[0] ? true : null });
        btn.addEventListener('click', function () {
          if (btn.disabled) return;
          picks[idx] = c;
          group.querySelectorAll('.cat-btn').forEach(function (x) { x.setAttribute('aria-pressed', String(x === btn)); });
          check.disabled = Object.keys(picks).length < card.options.length;
        });
        group.appendChild(btn);
      });
      var row = h('div', { class: 'cat-row' }, [h('span', { class: 'cat-row__item', text: card.options[idx] }), group]);
      row._idx = idx;
      return row;
    });
    article.appendChild(h('div', { class: 'cat-rows' }, rows));
    check.addEventListener('click', function () {
      var all = true;
      rows.forEach(function (row) {
        var ok = picks[row._idx] === card.answers[row._idx];
        all = all && ok;
        row.classList.add(ok ? 'is-correct' : 'is-wrong');
        row.querySelectorAll('.cat-btn').forEach(function (b) {
          b.disabled = true;
          if (b.textContent === card.answers[row._idx]) b.classList.add('is-answer');
        });
      });
      finish(all, null);
    });
    actions.appendChild(h('span', { class: 'step__hint', text: 'Choose a group for every item' }));
    actions.appendChild(check);
  }

  // Numeric: type a number; small rounding differences are accepted.
  function numeric(card, article, actions, finish) {
    article.appendChild(h('h2', { class: 'step__q', text: card.prompt }));
    var unit = card.answers[1] || '';
    var input = h('input', { class: 'answer-input answer-input--num', type: 'text', inputmode: 'decimal', autocomplete: 'off', placeholder: 'Your answer', 'aria-label': 'Your answer', 'data-autofocus': true });
    article.appendChild(h('div', { class: 'num-row' }, [input, unit ? h('span', { class: 'num-row__unit', text: unit }) : null]));
    var expected = parseFloat(card.answers[0]);
    var decimals = (card.answers[0].split('.')[1] || '').length;
    function grade(reveal) {
      var given = parseFloat(String(input.value).replace(/,/g, '').replace(/[^\d.eE+-]/g, ''));
      var tol = Math.max(Math.abs(expected) * 0.01, 0.5 * Math.pow(10, -decimals));
      var ok = !reveal && isFinite(given) && Math.abs(given - expected) <= tol + 1e-12;
      input.readOnly = true;
      input.classList.add(ok ? 'is-correct' : 'is-wrong');
      finish(ok, card.answers[0] + (unit ? ' ' + unit : ''));
    }
    var check = h('button', { type: 'button', class: 'btn btn--primary', text: 'Check' });
    var giveUp = h('button', { type: 'button', class: 'link-btn small', text: 'Show answer' });
    check.addEventListener('click', function () { if (input.value.trim()) grade(false); else input.focus(); });
    giveUp.addEventListener('click', function () { grade(true); });
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && input.value.trim()) { e.preventDefault(); e.stopPropagation(); grade(false); }
    });
    actions.appendChild(giveUp);
    actions.appendChild(check);
  }

  // Explain: write an answer, then tick which key points you covered.
  function explain(card, article, actions, finish) {
    article.appendChild(h('h2', { class: 'step__q', text: card.prompt }));
    var area = h('textarea', { class: 'answer-input', rows: '5', placeholder: 'Write your explanation in a few sentences…', 'aria-label': 'Your explanation', 'data-autofocus': true });
    article.appendChild(area);
    var reveal = h('button', { type: 'button', class: 'btn btn--primary', text: 'Compare with key points' });
    reveal.addEventListener('click', function () {
      area.readOnly = true;
      var boxes = card.answers.map(function (point) {
        return h('label', { class: 'keypoint' }, [h('input', { type: 'checkbox' }), h('span', { text: point })]);
      });
      var panel = h('div', { class: 'keypoints' }, [
        h('p', { class: 'keypoints__title', text: 'Tick the key points your answer covered:' })
      ].concat(boxes));
      article.insertBefore(panel, actions);
      var done = h('button', { type: 'button', class: 'btn btn--primary', text: 'Done' });
      done.addEventListener('click', function () {
        var ticked = boxes.filter(function (b) { return b.querySelector('input').checked; }).length;
        boxes.forEach(function (b) { b.querySelector('input').disabled = true; });
        var ok = ticked >= Math.ceil(card.answers.length * 0.6);
        finish(ok, ok ? null : 'Covered ' + ticked + ' of ' + card.answers.length + ' key points');
      });
      actions.innerHTML = '';
      actions.appendChild(h('span', { class: 'step__hint', text: 'Be honest, it helps you learn' }));
      actions.appendChild(done);
      done.focus({ preventScroll: true });
    });
    actions.appendChild(h('span', { class: 'step__hint', text: 'Self-marked against the key points' }));
    actions.appendChild(reveal);
  }

  // ---- results -----------------------------------------------------------
  function renderResults() {
    var correctCount = questions.filter(function (q) { return q.result === true; }).length;
    var score = Math.round(correctCount / questions.length * 100);
    var missed = questions.filter(function (q) { return q.result !== true; });
    var verdict = score >= 90 ? 'Excellent work.' : score >= 70 ? 'Good going. Review what you missed.' : score >= 40 ? 'Getting there. Another round will help.' : 'Worth another look at the notes.';

    var ring = h('div', { class: 'results__ring' }, [h('div', null, [h('p', { class: 'results__score', text: score + '%' })])]);
    ring.style.setProperty('--p', score);
    var timeText = data.timed ? ' Time: ' + formatTime(Date.now() - startedAt) + '.' : '';
    var meta = h('p', { class: 'muted', text: correctCount + ' of ' + questions.length + ' correct.' + timeText + ' ' + verdict });
    var extra = h('p', { class: 'muted small' });
    var buttons = h('div', { class: 'results__actions' });

    if (data.shared) {
      buttons.appendChild(h('a', { class: 'btn btn--primary btn--lg', href: '/login', text: 'Make quizzes from my own notes' }));
      extra.textContent = 'Free account. Upload slides or PDFs and get quizzes like this in seconds, plus a week of Pro free.';
    } else if (data.guest) {
      buttons.appendChild(h('a', { class: 'btn btn--primary btn--lg', href: '/login', text: 'Save this quiz with Google' }));
      extra.textContent = 'Free account. Your quiz, flashcards and score are saved to your library.';
    } else {
      if (missed.length && missed.length < questions.length) {
        var ids = missed.map(function (q) { return q.card.id; }).filter(function (id) { return typeof id === 'number'; });
        if (ids.length) buttons.appendChild(h('a', { class: 'btn btn--primary', href: data.retry_url + '?mode=missed&ids=' + ids.join(','), text: 'Retry the ' + ids.length + ' I missed' }));
      }
      buttons.appendChild(h('a', { class: 'btn', href: data.retry_url, text: 'Retake quiz' }));
      buttons.appendChild(h('a', { class: 'btn btn--ghost', href: data.set_url, text: 'Back to set' }));
    }

    var article = h('article', { class: 'step results' }, [
      h('p', { class: 'step__kind', text: 'Quiz complete' }), ring, meta, buttons, extra
    ]);

    if (missed.length) {
      var review = h('section', { class: 'review' }, [h('h3', { text: 'Review what you missed' })]);
      missed.forEach(function (q) {
        var c = q.card;
        var answer = c.kind === 'true_false' ? (c.answers[0] === 'true' ? 'True' : 'False')
          : c.kind === 'ordering' ? c.options.join(' → ')
          : c.kind === 'matching' ? c.options.map(function (o, i) { return o + ' = ' + c.answers[i]; }).join(' · ')
          : c.kind === 'multi_select' ? c.answers.join(', ')
          : c.kind === 'categorize' ? c.options.map(function (o, i) { return o + ' → ' + c.answers[i]; }).join(' · ')
          : c.kind === 'numeric' ? c.answers[0] + (c.answers[1] ? ' ' + c.answers[1] : '')
          : c.kind === 'explain' ? 'Key points: ' + c.answers.join('; ')
          : c.kind === 'fill_blank' ? c.prompt.split('{blank}').reduce(function (acc, part, i) { return acc + part + (c.answers[i] !== undefined && i < c.answers.length ? '[' + c.answers[i] + ']' : ''); }, '')
          : c.answers[0];
        review.appendChild(h('div', { class: 'review__item' }, [
          h('p', null, [h('strong', { text: c.kind === 'fill_blank' ? 'Fill in the blank' : c.prompt })]),
          h('p', { class: 'review__a', text: answer }),
          c.explanation ? h('p', { class: 'muted small', text: c.explanation }) : null
        ]));
      });
      article.appendChild(review);
    }

    if (data.submit_url) {
      QN.request(data.submit_url, {
        body: { results: questions.map(function (q) { return { card_id: q.card.id, correct: q.result === true }; }) }
      }).then(function (res) {
        var parts = [];
        if (res.best !== null && res.best !== undefined) parts.push('Best score: ' + Math.round(res.best) + '%.');
        extra.textContent = parts.join(' ');
        if (res.next) {
          extra.appendChild(document.createTextNode(' Up next in this subject: '));
          extra.appendChild(h('a', { href: res.next.url, text: res.next.title }));
        }
      }).catch(function () {
        extra.textContent = 'Your score couldn’t be saved. Check your connection.';
      });
    }
    return article;
  }

  // ---- keyboard ----------------------------------------------------------
  document.addEventListener('keydown', function (e) {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    var tag = (e.target.tagName || '').toLowerCase();
    var article = root.querySelector('[data-stage] > article');
    if (!article) return;
    if (e.key === 'Enter' && tag !== 'input' && tag !== 'textarea' && tag !== 'button' && tag !== 'a') {
      var primary = article.querySelector('.step__actions .btn--primary');
      if (primary) { e.preventDefault(); primary.click(); }
      return;
    }
    if (tag !== 'input' && tag !== 'textarea' && tag !== 'select' && article._keyHandler && (e.key.length === 1 || e.key === 'ArrowLeft' || e.key === 'ArrowRight')) article._keyHandler(e.key);
  });

  // ---- mount ---------------------------------------------------------------
  progressFill = h('div', { class: 'progress__fill' });
  progressLabel = h('span', { class: 'progress__label' });
  root.appendChild(h('div', { class: 'progress', 'aria-hidden': 'true' }, [h('div', { class: 'progress__track' }, [progressFill]), progressLabel]));
  if (data.timed) {
    var clock = h('p', { class: 'quiz-clock', 'aria-label': 'Time elapsed', text: '0:00' });
    root.appendChild(clock);
    setInterval(function () { if (index < steps.length) clock.textContent = formatTime(Date.now() - startedAt); }, 1000);
  }
  root.appendChild(h('div', { 'data-stage': '' }));
  show(0);
})();
