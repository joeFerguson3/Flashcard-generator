/* Flashcards with spaced-repetition grading. */
(function () {
  'use strict';
  var dataEl = document.getElementById('deck-data');
  var root = document.getElementById('deck');
  if (!dataEl || !root) return;
  var data = JSON.parse(dataEl.textContent);
  var queue = data.cards.slice();
  var total = queue.length;
  var reviewed = 0, again = 0;
  var current = null, flipped = false;

  function h(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  }

  var counter = h('div', 'progress');
  var track = h('div', 'progress__track');
  var fill = h('div', 'progress__fill');
  var label = h('span', 'progress__label');
  track.appendChild(fill);
  counter.appendChild(track);
  counter.appendChild(label);

  var scene = h('div', 'fc-scene');
  var card = h('button', 'fc');
  card.type = 'button';
  card.setAttribute('aria-live', 'polite');
  var front = h('div', 'fc__face fc__face--front');
  var back = h('div', 'fc__face fc__face--back');
  card.appendChild(front);
  card.appendChild(back);
  scene.appendChild(card);

  var grades = h('div', 'grades');
  [['again', 'Again', '< 1 min'], ['hard', 'Hard', 'soon'], ['good', 'Good', 'later'], ['easy', 'Easy', 'much later']].forEach(function (g, i) {
    var b = h('button', 'grade grade--' + g[0]);
    b.type = 'button';
    b.appendChild(document.createTextNode(g[1]));
    b.appendChild(h('small', null, (i + 1) + ' · ' + g[2]));
    b.addEventListener('click', function () { grade(g[0]); });
    grades.appendChild(b);
  });
  var hint = h('p', 'deck__hint', 'Tap the card or press Space to flip.');

  root.appendChild(counter);
  root.appendChild(scene);
  root.appendChild(grades);
  root.appendChild(hint);

  function face(el, labelText, text) {
    el.innerHTML = '';
    el.appendChild(h('span', 'fc__label', labelText));
    el.appendChild(h('div', 'fc__text', text));
    if (labelText === 'Question') el.appendChild(h('span', 'fc__tap', 'Tap to reveal'));
  }

  function showNext() {
    current = queue.shift();
    if (!current) return done();
    flipped = false;
    card.classList.remove('is-flipped');
    // Swap text after the flip-back finishes so the answer isn't glimpsed.
    setTimeout(function () {
      face(front, 'Question', current.front);
      face(back, 'Answer', current.back);
    }, card.dataset.started ? 200 : 0);
    card.dataset.started = '1';
    grades.style.visibility = 'hidden';
    fill.style.width = (reviewed / Math.max(total, 1) * 100) + '%';
    label.textContent = (reviewed + 1) + ' / ' + total;
  }

  function flip() {
    if (!current) return;
    flipped = !flipped;
    card.classList.toggle('is-flipped', flipped);
    if (flipped) grades.style.visibility = 'visible';
  }

  function grade(value) {
    if (!current || !flipped) return;
    var c = current;
    QN.request(data.review_url.replace('{id}', c.id), { body: { grade: value } }).catch(function (err) {
      QN.toast(err.message, 'error');
    });
    if (value === 'again') {
      again++;
      queue.push(c); // see it again this session
      total++;
    }
    reviewed++;
    showNext();
  }

  function done() {
    root.innerHTML = '';
    var box = h('div', 'step results');
    box.appendChild(h('p', 'step__kind', 'Session complete'));
    box.appendChild(h('p', 'results__score', '✓'));
    var unique = data.cards.length;
    box.appendChild(h('p', 'muted', 'You reviewed ' + unique + ' card' + (unique === 1 ? '' : 's') + (again ? ', and repeated the ' + again + ' you found hardest.' : '.') + ' Cards will come back when they’re due.'));
    var actions = h('div', 'results__actions');
    var a1 = h('a', 'btn btn--primary', 'Back to set');
    a1.href = data.set_url;
    var a2 = h('a', 'btn', 'Review all cards again');
    a2.href = window.location.pathname + '?mode=all';
    actions.appendChild(a1);
    actions.appendChild(a2);
    box.appendChild(actions);
    root.appendChild(box);
  }

  card.addEventListener('click', flip);
  document.addEventListener('keydown', function (e) {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.key === ' ' || e.key === 'Enter') {
      if (document.activeElement && document.activeElement.classList.contains('grade')) return;
      e.preventDefault();
      flip();
    } else if (flipped && ['1', '2', '3', '4'].indexOf(e.key) !== -1) {
      grade(['again', 'hard', 'good', 'easy'][parseInt(e.key, 10) - 1]);
    }
  });

  showNext();
})();
