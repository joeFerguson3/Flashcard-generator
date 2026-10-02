/* Notes editor: topics -> sections -> points, with autosave.
 *
 * Points are edited as plain text, one per line. Indentation (2 spaces per
 * level, or Tab) sets the level: "Key idea" / "  detail" / "    example".
 */
(function () {
  'use strict';
  var dataEl = document.getElementById('notes-data');
  if (!dataEl) return;
  var config = JSON.parse(dataEl.textContent);
  var editor = document.querySelector('[data-editor]');
  var saveState = document.querySelector('[data-save-state]');
  var titleInput = document.querySelector('[data-title]');
  var subjectInput = document.querySelector('[data-subject]');
  var overlay = document.querySelector('[data-overlay]');
  var errorEl = document.querySelector('[data-gen-bar] [data-error]');

  // ---- model <-> text --------------------------------------------------
  function pointsToText(points) {
    return (points || []).map(function (p) {
      return '  '.repeat(Math.max(0, (p.level || 1) - 1)) + p.text;
    }).join('\n');
  }
  function textToPoints(text) {
    return text.split('\n').map(function (line) {
      var m = line.replace(/\t/g, '  ').match(/^(\s*)(?:[-*•]\s*)?(.*)$/);
      var text = (m[2] || '').trim();
      if (!text) return null;
      var level = Math.min(3, Math.floor(m[1].length / 2) + 1);
      return { text: text, level: level };
    }).filter(Boolean);
  }

  // ---- rendering ---------------------------------------------------------
  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === 'text') node.textContent = attrs[k];
      else if (k === 'value') node.value = attrs[k];
      else node.setAttribute(k, attrs[k]);
    });
    (children || []).forEach(function (c) { if (c) node.appendChild(c); });
    return node;
  }

  function autosize(textarea) {
    textarea.style.height = 'auto';
    textarea.style.height = (textarea.scrollHeight + 2) + 'px';
  }

  function renderSection(section) {
    var sub = el('input', { value: section.subheading || '', 'aria-label': 'Section title', 'data-sub': '', maxlength: '200' });
    var del = el('button', { type: 'button', class: 'icon-btn', 'aria-label': 'Delete section', text: 'Delete' });
    var area = el('textarea', { 'aria-label': 'Points', rows: '2', spellcheck: 'true', 'data-points': '' });
    area.value = pointsToText(section.points);
    var node = el('div', { class: 'sec', 'data-sec': '' }, [el('div', { class: 'sec__head' }, [sub, del]), area]);
    if (section.id) node.dataset.id = section.id;
    del.addEventListener('click', function () {
      var topic = node.closest('[data-topic]');
      node.remove();
      if (!topic.querySelector('[data-sec]')) topic.remove();
      changed();
    });
    area.addEventListener('keydown', handleTab);
    area.addEventListener('input', function () { autosize(area); });
    requestAnimationFrame(function () { autosize(area); });
    return node;
  }

  function renderTopic(heading, sections) {
    var input = el('input', { value: heading || '', 'aria-label': 'Topic', 'data-heading': '', maxlength: '200' });
    var improve = el('button', { type: 'button', class: 'icon-btn icon-btn--hl', title: 'Let AI tidy up and fill gaps in this topic', text: '✦ Improve' });
    var del = el('button', { type: 'button', class: 'icon-btn', text: 'Delete topic' });
    var body = el('div', { 'data-secs': '' }, sections.map(renderSection));
    var add = el('button', { type: 'button', class: 'icon-btn', text: '+ Add section' });
    var topic = el('section', { class: 'topic', 'data-topic': '' }, [
      el('div', { class: 'topic__head' }, [input, improve, del]),
      body,
      el('div', { class: 'topic__foot' }, [add])
    ]);
    add.addEventListener('click', function () {
      var s = renderSection({ subheading: '', points: [] });
      body.appendChild(s);
      s.querySelector('input').focus();
    });
    del.addEventListener('click', function () {
      if (!window.confirm('Delete the topic "' + (input.value || 'Untitled') + '" and all its sections?')) return;
      topic.remove();
      changed();
    });
    improve.addEventListener('click', function () { enhanceTopic(topic); });
    return topic;
  }

  function render(sections) {
    editor.innerHTML = '';
    var groups = [];
    sections.forEach(function (s) {
      if (!groups.length || groups[groups.length - 1].heading !== s.heading) groups.push({ heading: s.heading, sections: [] });
      groups[groups.length - 1].sections.push(s);
    });
    groups.forEach(function (g) { editor.appendChild(renderTopic(g.heading, g.sections)); });
  }

  function collect() {
    var out = [];
    editor.querySelectorAll('[data-topic]').forEach(function (topic) {
      var heading = topic.querySelector('[data-heading]').value.trim() || 'Untitled topic';
      topic.querySelectorAll('[data-sec]').forEach(function (sec) {
        var points = textToPoints(sec.querySelector('[data-points]').value);
        var sub = sec.querySelector('[data-sub]').value.trim();
        if (!points.length && !sub) return;
        out.push({ id: sec.dataset.id ? parseInt(sec.dataset.id, 10) : null, heading: heading, subheading: sub || heading, points: points });
      });
    });
    return out;
  }

  function handleTab(e) {
    if (e.key !== 'Tab') return;
    e.preventDefault();
    var ta = e.target;
    var start = ta.selectionStart, end = ta.selectionEnd, v = ta.value;
    var lineStart = v.lastIndexOf('\n', start - 1) + 1;
    var lineEnd = v.indexOf('\n', end);
    if (lineEnd === -1) lineEnd = v.length;
    var original = v.slice(lineStart, lineEnd);
    var block = original.split('\n');
    var updated = block.map(function (line) {
      if (e.shiftKey) return line.replace(/^ {1,2}/, '');
      return line.match(/^ {4}/) ? line : '  ' + line;
    }).join('\n');
    ta.value = v.slice(0, lineStart) + updated + v.slice(lineEnd);
    if (block.length > 1) {
      ta.selectionStart = lineStart;
      ta.selectionEnd = lineStart + updated.length;
    } else {
      ta.selectionStart = ta.selectionEnd = Math.max(lineStart, start + updated.length - original.length);
    }
    changed();
  }

  // ---- autosave ----------------------------------------------------------
  var timer = null, saving = null, dirty = false;
  function setState(text, cls) {
    saveState.textContent = text;
    saveState.className = 'save-state muted small' + (cls ? ' ' + cls : '');
  }
  function changed() {
    dirty = true;
    setState('Unsaved changes');
    clearTimeout(timer);
    timer = setTimeout(save, 1200);
  }
  function save() {
    clearTimeout(timer);
    if (saving) return saving.then(function () { return dirty ? save() : null; });
    if (!dirty) return Promise.resolve();
    dirty = false;
    setState('Saving…', 'is-saving');
    saving = QN.request(config.save_url, {
      method: 'PUT',
      body: { title: titleInput.value, subject: subjectInput.value, sections: collect() }
    }).then(function (res) {
      // Give new sections their ids so later saves update rather than duplicate.
      var nodes = editor.querySelectorAll('[data-sec]');
      var withContent = Array.prototype.filter.call(nodes, function (n) {
        return textToPoints(n.querySelector('[data-points]').value).length || n.querySelector('[data-sub]').value.trim();
      });
      if (res.sections && res.sections.length === withContent.length) {
        withContent.forEach(function (n, i) { n.dataset.id = res.sections[i].id; });
      }
      setState(dirty ? 'Unsaved changes' : 'All changes saved');
    }).catch(function (err) {
      dirty = true;
      setState('Not saved: ' + err.message, 'is-error');
    }).then(function () { saving = null; });
    return saving;
  }

  editor.addEventListener('input', changed);
  titleInput.addEventListener('input', changed);
  subjectInput.addEventListener('input', changed);
  window.addEventListener('beforeunload', function (e) {
    if (dirty || saving) { e.preventDefault(); e.returnValue = ''; }
  });
  document.querySelector('[data-add-topic]').addEventListener('click', function () {
    var t = renderTopic('', [{ subheading: '', points: [] }]);
    editor.appendChild(t);
    t.querySelector('input').focus();
  });

  // ---- AI improve --------------------------------------------------------
  function enhanceTopic(topic) {
    var heading = topic.querySelector('[data-heading]').value.trim();
    var sections = [];
    topic.querySelectorAll('[data-sec]').forEach(function (sec) {
      sections.push({ heading: heading, subheading: sec.querySelector('[data-sub]').value, points: textToPoints(sec.querySelector('[data-points]').value) });
    });
    if (!sections.length) return;
    topic.classList.add('is-busy');
    var btn = topic.querySelector('.icon-btn--hl');
    btn.textContent = 'Improving…';
    QN.request(config.enhance_url, { body: { heading: heading, sections: sections } })
      .then(function (res) {
        var fresh = renderTopic(heading, res.sections);
        topic.replaceWith(fresh);
        changed();
        QN.toast('Topic improved. Review the changes, they save automatically.');
      })
      .catch(function (err) {
        topic.classList.remove('is-busy');
        btn.textContent = '✦ Improve';
        QN.toast(err.message, 'error');
      });
  }

  // ---- generate quiz -----------------------------------------------------
  document.querySelector('[data-generate]').addEventListener('click', function () {
    errorEl.hidden = true;
    var kinds = Array.prototype.map.call(document.querySelectorAll('[data-kind]:checked'), function (c) { return c.value; });
    if (!kinds.length) {
      errorEl.textContent = 'Pick at least one question type.';
      errorEl.hidden = false;
      return;
    }
    var sections = collect();
    if (!sections.length) {
      errorEl.textContent = 'Add some notes first.';
      errorEl.hidden = false;
      return;
    }
    if (config.has_attempts && !window.confirm('This replaces the current questions and flashcards (your past scores are kept). Continue?')) return;
    var difficulty = (document.querySelector('input[name="difficulty"]:checked') || {}).value || 'medium';
    overlay.hidden = false;
    var stop = QN.startLoader(overlay, ['Reading your notes…', 'Choosing what to test…', 'Writing questions…', 'Writing flashcards…', 'Checking answers…', 'Almost there…']);
    save().then(function () {
      return QN.request(config.generate_url, {
        body: {
          sections: collect(),
          count: document.querySelector('[data-count]').value || null,
          difficulty: difficulty,
          kinds: kinds
        }
      });
    }).then(function (res) {
      dirty = false;
      window.location.href = res.redirect;
    }).catch(function (err) {
      stop();
      overlay.hidden = true;
      errorEl.textContent = err.message;
      errorEl.hidden = false;
    });
  });

  render(config.sections);
  if (!config.sections.length) document.querySelector('[data-add-topic]').click();
})();
