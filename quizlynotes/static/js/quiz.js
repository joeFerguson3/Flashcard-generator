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
    short_answer: 'Short answer', ordering: 'Put in order'
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
  function renderNotes(step) {
    var body = [h('p', { class: 'step__kind', text: 'Read first' }), h('h2', { text: step.group.heading })];
    step.group.notes.forEach(function (n) {
      if (n.subheading && n.subheading !== step.group.heading) body.push(h('h3', { text: n.subheading }));
      body.push(h('ul', { class: 'points' }, (n.points || []).map(function (p) {
        return h('li', { class: 'lvl-' + (p.level || 1), text: p.text });
      })));
    });
    var count = step.group.cards.length;
    body.push(h('div', { class: 'step__actions' }, [
      h('span', { class: 'step__hint', text: count + ' question' + (count === 1 ? '' : 's') + ' on this topic' }),
      h('button', { class: 'btn btn--primary', type: 'button', 'data-autofocus': true, onclick: next, text: 'I’m ready →' })
    ]));
    return h('article', { class: 'step step--notes' }, body);
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

    var renderers = { multiple_choice: mcq, true_false: tf, fill_blank: blanks, short_answer: shortAnswer, ordering: ordering };
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

  // ---- results -----------------------------------------------------------
  function renderResults() {
    var correctCount = questions.filter(function (q) { return q.result === true; }).length;
    var score = Math.round(correctCount / questions.length * 100);
    var missed = questions.filter(function (q) { return q.result !== true; });
    var verdict = score >= 90 ? 'Excellent work.' : score >= 70 ? 'Good going. Review what you missed.' : score >= 40 ? 'Getting there. Another round will help.' : 'Worth another look at the notes.';

    var ring = h('div', { class: 'results__ring' }, [h('div', null, [h('p', { class: 'results__score', text: score + '%' })])]);
    ring.style.setProperty('--p', score);
    var meta = h('p', { class: 'muted', text: correctCount + ' of ' + questions.length + ' correct. ' + verdict });
    var extra = h('p', { class: 'muted small' });
    var buttons = h('div', { class: 'results__actions' });

    if (data.guest) {
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
    if (tag !== 'input' && tag !== 'textarea' && article._keyHandler && e.key.length === 1) article._keyHandler(e.key);
  });

  // ---- mount ---------------------------------------------------------------
  progressFill = h('div', { class: 'progress__fill' });
  progressLabel = h('span', { class: 'progress__label' });
  root.appendChild(h('div', { class: 'progress', 'aria-hidden': 'true' }, [h('div', { class: 'progress__track' }, [progressFill]), progressLabel]));
  root.appendChild(h('div', { 'data-stage': '' }));
  show(0);
})();
