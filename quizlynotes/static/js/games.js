/* Study games: Match, Speed round, Write it.
 * Built from the set's flashcards (and multiple-choice / true-false questions
 * for Speed round). Best scores are kept in this browser.
 */
(function () {
  'use strict';
  var root = document.getElementById('game');
  var dataEl = document.getElementById('game-data');
  if (!root || !dataEl) return;
  var data = JSON.parse(dataEl.textContent);

  // ---- helpers -----------------------------------------------------------
  function h(tag, attrs, children) {
    var n = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      var v = attrs[k];
      if (v === null || v === undefined || v === false) return;
      if (k === 'text') n.textContent = v;
      else if (k === 'class') n.className = v;
      else if (k.slice(0, 2) === 'on') n.addEventListener(k.slice(2), v);
      else n.setAttribute(k, v === true ? '' : v);
    });
    (children || []).forEach(function (c) {
      if (c === null || c === undefined || c === false) return;
      n.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    });
    return n;
  }
  function shuffle(list) {
    var a = list.slice();
    for (var i = a.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var t = a[i]; a[i] = a[j]; a[j] = t;
    }
    return a;
  }
  function bestKey() { return 'qn-best-' + data.set_id + '-' + data.game; }
  function getBest() {
    try { var v = localStorage.getItem(bestKey()); return v === null ? null : parseFloat(v); } catch (e) { return null; }
  }
  function setBest(v) { try { localStorage.setItem(bestKey(), String(v)); } catch (e) {} }
  function mount(node) {
    root.innerHTML = '';
    root.appendChild(node);
    var f = node.querySelector('[data-autofocus]');
    if (f) f.focus({ preventScroll: true });
  }
  var keyHandler = null;
  document.addEventListener('keydown', function (e) {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    if (keyHandler) keyHandler(e);
  });

  var STOP = ['the', 'a', 'an', 'of', 'to', 'in', 'and', 'or', 'is', 'are', 'was', 'were', 'it', 'its', 'by',
    'for', 'on', 'with', 'as', 'at', 'that', 'this', 'be', 'from', 'into', 'their', 'they', 'which'];
  function normalise(s) {
    return String(s || '').toLowerCase().normalize('NFKD').replace(/[̀-ͯ]/g, '')
      .replace(/[^\p{L}\p{N}\s.]/gu, ' ').replace(/\s+/g, ' ').trim();
  }
  function levenshtein(a, b) {
    if (a === b) return 0;
    var prev = [], cur, i, j;
    for (j = 0; j <= b.length; j++) prev[j] = j;
    for (i = 1; i <= a.length; i++) {
      cur = [i];
      for (j = 1; j <= b.length; j++) cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
      prev = cur;
    }
    return prev[b.length];
  }
  function closeWord(a, b) {
    if (a === b) return true;
    if (a.replace(/s$/, '') === b.replace(/s$/, '')) return true;
    var allowed = b.length <= 4 ? 0 : b.length <= 8 ? 1 : 2;
    return levenshtein(a, b) <= allowed;
  }
  /* Grade a typed answer against a sentence-length answer: correct when the
     typed text covers most of the answer's key words (typos allowed). */
  function grade(given, expected) {
    var g = normalise(given), e = normalise(expected);
    if (!g) return false;
    if (g === e || levenshtein(g, e) <= Math.floor(e.length * 0.15)) return true;
    var keys = e.split(' ').filter(function (w) { return w.length > 2 && STOP.indexOf(w) === -1; });
    if (!keys.length) keys = e.split(' ');
    var words = g.split(' ');
    var hit = keys.filter(function (k) { return words.some(function (w) { return closeWord(w, k); }); }).length;
    var needed = keys.length <= 2 ? keys.length : Math.ceil(keys.length * 0.6);
    return hit >= needed;
  }

  function intro(title, blurb, startLabel, onStart) {
    var best = getBest();
    var start = h('button', { class: 'btn btn--primary btn--lg', type: 'button', 'data-autofocus': true, text: startLabel, onclick: onStart });
    mount(h('article', { class: 'step game-intro' }, [
      h('p', { class: 'step__kind', text: 'Game' }),
      h('h1', { class: 'player-title', text: title }),
      h('p', { class: 'muted', text: blurb }),
      best !== null ? h('p', { class: 'game-best', text: 'Your best: ' + (data.game === 'match' ? best.toFixed(1) + 's' : best) }) : null,
      h('div', { class: 'results__actions' }, [start])
    ]));
    keyHandler = function (e) { if (e.key === 'Enter') { e.preventDefault(); onStart(); } };
  }

  function finish(opts) {
    keyHandler = null;
    var isNewBest = false;
    if (opts.bestValue !== undefined) {
      var best = getBest();
      var better = best === null || (opts.lowerIsBetter ? opts.bestValue < best : opts.bestValue > best);
      if (better) { setBest(opts.bestValue); isNewBest = best !== null; }
    }
    var again = h('button', { class: 'btn btn--primary', type: 'button', 'data-autofocus': true, text: 'Play again', onclick: start });
    var node = h('article', { class: 'step results' }, [
      h('p', { class: 'step__kind', text: opts.kicker || 'Finished' }),
      h('p', { class: 'results__score', text: opts.headline }),
      h('p', { class: 'muted', text: opts.detail }),
      isNewBest ? h('p', { class: 'game-best game-best--new', text: 'New personal best!' })
        : (getBest() !== null ? h('p', { class: 'game-best', text: 'Your best: ' + opts.formatBest(getBest()) }) : null),
      h('div', { class: 'results__actions' }, [again, h('a', { class: 'btn btn--ghost', href: data.set_url, text: 'Back to set' })])
    ]);
    if (opts.review && opts.review.length) {
      var review = h('section', { class: 'review' }, [h('h3', { text: 'Worth another look' })]);
      opts.review.forEach(function (r) {
        review.appendChild(h('div', { class: 'review__item' }, [
          h('p', null, [h('strong', { text: r.q })]), h('p', { class: 'review__a', text: r.a })
        ]));
      });
      node.appendChild(review);
    }
    mount(node);
    keyHandler = function (e) { if (e.key === 'Enter' && document.activeElement === document.body) start(); };
  }

  // ---- Match ---------------------------------------------------------------
  function match() {
    var pairs = shuffle(data.flashcards).slice(0, 6);
    var tiles = [];
    pairs.forEach(function (c, i) {
      tiles.push({ pair: i, side: 'front', text: c.front });
      tiles.push({ pair: i, side: 'back', text: c.back });
    });
    tiles = shuffle(tiles);
    var left = pairs.length, penalty = 0, startTime = 0, timerId = null, selected = null, locked = false;
    var clock = h('span', { class: 'game-clock', text: '0.0s' });
    var grid = h('div', { class: 'match-grid', role: 'group', 'aria-label': 'Match the pairs' });
    tiles.forEach(function (t) {
      var btn = h('button', { type: 'button', class: 'match-tile match-tile--' + t.side }, [h('span', { text: t.text })]);
      btn._tile = t;
      btn.addEventListener('click', function () { pick(btn); });
      grid.appendChild(btn);
    });
    function elapsed() { return (Date.now() - startTime) / 1000 + penalty; }
    function pick(btn) {
      if (locked || btn.classList.contains('is-matched')) return;
      if (!selected) { selected = btn; btn.classList.add('is-selected'); return; }
      if (selected === btn) { btn.classList.remove('is-selected'); selected = null; return; }
      var a = selected, b = btn;
      selected = null;
      if (a._tile.pair === b._tile.pair) {
        a.classList.remove('is-selected');
        [a, b].forEach(function (x) { x.classList.add('is-matched'); x.disabled = true; });
        left--;
        if (!left) done();
      } else {
        locked = true;
        penalty += 1;
        b.classList.add('is-selected');
        [a, b].forEach(function (x) { x.classList.add('is-wrong'); });
        clock.classList.add('is-penalty');
        setTimeout(function () {
          [a, b].forEach(function (x) { x.classList.remove('is-wrong', 'is-selected'); });
          clock.classList.remove('is-penalty');
          locked = false;
        }, 600);
      }
    }
    function done() {
      clearInterval(timerId);
      var t = Math.round(elapsed() * 10) / 10;
      setTimeout(function () {
        finish({
          kicker: 'All matched', headline: t.toFixed(1) + 's',
          detail: pairs.length + ' pairs' + (penalty ? ', including ' + penalty + 's of penalties for wrong pairs.' : ' with no mistakes.'),
          bestValue: t, lowerIsBetter: true, formatBest: function (v) { return v.toFixed(1) + 's'; }
        });
      }, 350);
    }
    mount(h('div', { class: 'game-board' }, [
      h('div', { class: 'game-hud' }, [h('span', { class: 'muted small', text: 'Tap a term, then its match. Wrong pairs add 1 second.' }), clock]),
      grid
    ]));
    startTime = Date.now();
    timerId = setInterval(function () { clock.textContent = elapsed().toFixed(1) + 's'; }, 100);
    keyHandler = null;
  }

  // ---- Speed round ---------------------------------------------------------
  function buildSpeedPool() {
    var pool = data.choices.map(function (c) {
      return { prompt: c.prompt, options: c.options.slice(), answer: c.answer };
    });
    var backs = data.flashcards.map(function (c) { return c.back; });
    if (data.flashcards.length >= 4) {
      data.flashcards.forEach(function (c) {
        var wrong = shuffle(backs.filter(function (b) { return b !== c.back; })).slice(0, 3);
        pool.push({ prompt: c.front, options: wrong.concat([c.back]), answer: c.back });
      });
    }
    return pool;
  }
  function speed() {
    var DURATION = 60;
    var pool = buildSpeedPool(), queue = [];
    var score = 0, streak = 0, bestStreak = 0, answered = 0, correct = 0, missed = [], over = false, busy = false;
    var ends = Date.now() + DURATION * 1000;
    var bar = h('div', { class: 'progress__fill progress__fill--time' });
    var timeLabel = h('span', { class: 'progress__label', text: DURATION + 's' });
    var scoreEl = h('span', { class: 'game-score', text: '0' });
    var streakEl = h('span', { class: 'game-streak' });
    var stage = h('div');
    mount(h('div', { class: 'game-board' }, [
      h('div', { class: 'progress' }, [h('div', { class: 'progress__track' }, [bar]), timeLabel]),
      h('div', { class: 'game-hud' }, [h('span', null, ['Score ', scoreEl]), streakEl]),
      stage
    ]));
    var tick = setInterval(function () {
      var left = Math.max(0, (ends - Date.now()) / 1000);
      bar.style.width = (left / DURATION * 100) + '%';
      timeLabel.textContent = Math.ceil(left) + 's';
      if (left <= 0) end();
    }, 100);

    function nextQuestion() {
      if (over) return;
      if (!queue.length) queue = shuffle(pool);
      var q = queue.shift();
      var opts = q.options.length === 2 ? q.options : shuffle(q.options);
      var buttons = opts.map(function (o, i) {
        var b = h('button', { type: 'button', class: 'opt' }, [h('span', { class: 'opt__key', text: String(i + 1) }), h('span', { text: o })]);
        b.addEventListener('click', function () { choose(b, o); });
        return b;
      });
      stage.innerHTML = '';
      stage.appendChild(h('article', { class: 'step step--speed' }, [
        h('h2', { class: 'step__q', text: q.prompt }),
        h('div', { class: 'options' + (opts.length === 2 ? ' tf' : '') }, buttons)
      ]));
      busy = false;
      function choose(btn, value) {
        if (busy || over) return;
        busy = true;
        answered++;
        var ok = value === q.answer;
        buttons.forEach(function (b) {
          b.disabled = true;
          if (b.lastChild.textContent === q.answer) b.classList.add('is-correct');
          else if (b === btn) b.classList.add('is-wrong');
        });
        if (ok) {
          correct++;
          streak++;
          bestStreak = Math.max(bestStreak, streak);
          score += 10 + Math.min(streak - 1, 5) * 2;
        } else {
          streak = 0;
          missed.push({ q: q.prompt, a: q.answer });
        }
        scoreEl.textContent = score;
        streakEl.textContent = streak >= 2 ? streak + ' in a row' : '';
        streakEl.classList.toggle('is-hot', streak >= 3);
        setTimeout(nextQuestion, ok ? 250 : 1100);
      }
      keyHandler = function (e) {
        var n = parseInt(e.key, 10);
        if (n >= 1 && n <= buttons.length) { e.preventDefault(); buttons[n - 1].click(); }
      };
    }
    function end() {
      if (over) return;
      over = true;
      clearInterval(tick);
      var unique = [];
      missed.forEach(function (m) { if (!unique.some(function (u) { return u.q === m.q; })) unique.push(m); });
      finish({
        kicker: 'Time’s up', headline: String(score),
        detail: correct + ' of ' + answered + ' correct · best streak ' + bestStreak,
        bestValue: score, lowerIsBetter: false, formatBest: function (v) { return v; },
        review: unique.slice(0, 8)
      });
    }
    nextQuestion();
  }

  // ---- Write it ------------------------------------------------------------
  function write() {
    var queue = shuffle(data.flashcards), retry = [], round = 1, firstTry = 0, total = queue.length, seen = 0;
    var progress = h('div', { class: 'progress__fill' });
    var label = h('span', { class: 'progress__label' });
    var stage = h('div');
    mount(h('div', { class: 'game-board' }, [h('div', { class: 'progress' }, [h('div', { class: 'progress__track' }, [progress]), label]), stage]));

    function next() {
      if (!queue.length) {
        if (retry.length && round === 1) {
          round = 2;
          queue = shuffle(retry);
          retry = [];
          QN.toast('Round 2: the ones you missed.');
        } else {
          return finish({
            kicker: 'Done', headline: firstTry + '/' + total,
            detail: 'right first time' + (round === 2 ? ', then a second go at the rest.' : '.'),
            bestValue: Math.round(firstTry / total * 100), lowerIsBetter: false,
            formatBest: function (v) { return v + '% first time'; }
          });
        }
      }
      var card = queue.shift();
      if (round === 1) seen++;
      progress.style.width = ((round === 1 ? seen - 1 : total) / total * 100) + '%';
      label.textContent = round === 1 ? seen + ' / ' + total : 'Round 2';
      var input = h('textarea', { class: 'answer-input', rows: '2', placeholder: 'Type the answer from memory…', 'aria-label': 'Your answer', 'data-autofocus': true });
      var check = h('button', { type: 'button', class: 'btn btn--primary', text: 'Check' });
      var reveal = h('button', { type: 'button', class: 'link-btn small', text: 'I don’t know' });
      var actions = h('div', { class: 'step__actions' }, [reveal, check]);
      var art = h('article', { class: 'step' }, [
        h('p', { class: 'step__kind', text: 'Write it' }),
        h('h2', { class: 'step__q', text: card.front }), input, actions
      ]);
      stage.innerHTML = '';
      stage.appendChild(art);
      input.focus({ preventScroll: true });

      function mark(ok, gaveUp) {
        input.readOnly = true;
        input.classList.add(ok ? 'is-correct' : 'is-wrong');
        if (ok && round === 1) firstTry++;
        if (!ok) retry.push(card);
        var cont = h('button', { type: 'button', class: 'btn btn--primary', text: 'Continue →', onclick: next });
        var fb = h('div', { class: 'feedback ' + (ok ? 'feedback--good' : 'feedback--bad') }, [
          h('p', { class: 'feedback__title', text: ok ? 'Correct' : (gaveUp ? 'Here’s the answer' : 'Not quite') }),
          h('p', { class: 'feedback__answer' }, [h('strong', { text: card.back })])
        ]);
        if (!ok && !gaveUp) {
          var override = h('button', { type: 'button', class: 'link-btn small', text: 'I was right, count it', onclick: function () {
            retry.pop();
            if (round === 1) firstTry++;
            fb.className = 'feedback feedback--good';
            fb.querySelector('.feedback__title').textContent = 'Counted as correct';
            override.remove();
          } });
          fb.appendChild(h('p', { class: 'feedback__override' }, [override]));
        }
        art.insertBefore(fb, actions);
        actions.innerHTML = '';
        actions.appendChild(h('span', { class: 'step__hint', text: 'Press Enter to continue' }));
        actions.appendChild(cont);
        cont.focus({ preventScroll: true });
        keyHandler = null;
      }
      check.addEventListener('click', function () {
        if (!input.value.trim()) return input.focus();
        mark(grade(input.value, card.back), false);
      });
      reveal.addEventListener('click', function () { mark(false, true); });
      input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); check.click(); }
      });
    }
    next();
  }

  // ---- start -----------------------------------------------------------------
  var GAMES = {
    match: { title: 'Match', blurb: 'Six terms and their answers are scattered on the board. Pair them up as fast as you can. A wrong pair adds a one-second penalty.', run: match },
    speed: { title: 'Speed round', blurb: '60 seconds on the clock. Answer as many questions as you can. Correct answers in a row earn bonus points. Use keys 1 to 4 to answer fast.', run: speed },
    write: { title: 'Write it', blurb: 'See the question, type the answer from memory, then check. Anything you miss comes back for a second round.', run: write }
  };
  var game = GAMES[data.game];
  function start() { keyHandler = null; game.run(); }
  intro(game.title, game.blurb, 'Start', start);
})();
