/* Notes editor: topics -> sections -> bullet points, with autosave.
 * Each point is its own row; Tab / Shift+Tab sets its level (1-3).
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
    textarea.style.height = textarea.scrollHeight + 'px';
  }

  /* One bullet point = one auto-growing textarea.
     Enter: new point, Backspace on empty: remove, Tab / Shift+Tab: indent. */
  /* Each point shows as formatted text (key point, card or detail, with a
     bold "Term:"), and turns into a textarea when you click it. */
  function paintView(view, text) {
    view.textContent = '';
    if (!text.trim()) { view.appendChild(el('span', { class: 'pt__placeholder', text: 'Add a point…' })); return; }
    var i = text.indexOf(': ');
    if (i > 0 && i < 48) {
      view.appendChild(el('strong', { text: text.slice(0, i) }));
      view.appendChild(document.createTextNode(text.slice(i)));
    } else view.appendChild(document.createTextNode(text));
  }
  function startEdit(li) {
    if (li.classList.contains('is-editing')) return;
    li.classList.add('is-editing');
    autosize(li.querySelector('textarea'));
  }
  function renderPoint(point) {
    var ta = el('textarea', { rows: '1', class: 'pt__text', 'aria-label': 'Point', placeholder: 'Add a point…', spellcheck: 'true' });
    ta.value = point.text || '';
    var view = el('div', { class: 'pt__view', tabindex: '0', role: 'button', 'aria-label': 'Edit point' });
    paintView(view, ta.value);
    var li = el('li', { class: 'pt', 'data-pt': '' }, [view, ta]);
    setLevel(li, point.level || 1);
    if (!ta.value) li.classList.add('is-editing');
    view.addEventListener('click', function () { focusAt(ta, 'end'); });
    view.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); focusAt(ta, 'end'); }
    });
    ta.addEventListener('input', function () { autosize(ta); });
    ta.addEventListener('focus', function () { startEdit(li); });
    ta.addEventListener('blur', function () {
      paintView(view, ta.value);
      if (ta.value.trim()) li.classList.remove('is-editing');
    });
    ta.addEventListener('keydown', onPointKey);
    ta.addEventListener('paste', onPointPaste);
    requestAnimationFrame(function () { autosize(ta); });
    return li;
  }
  function setLevel(li, level) {
    level = Math.max(1, Math.min(3, level));
    li.dataset.level = level;
    li.classList.remove('lvl-1', 'lvl-2', 'lvl-3');
    li.classList.add('pt', 'lvl-' + level);
  }
  function focusAt(ta, pos) {
    startEdit(ta.closest('[data-pt]'));
    ta.focus();
    pos = pos === 'end' ? ta.value.length : pos;
    ta.setSelectionRange(pos, pos);
  }
  function onPointKey(e) {
    var ta = e.target, li = ta.closest('[data-pt]');
    var level = parseInt(li.dataset.level, 10);
    var atStart = ta.selectionStart === 0 && ta.selectionEnd === 0;
    var atEnd = ta.selectionStart === ta.value.length;
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      var after = ta.value.slice(ta.selectionEnd);
      ta.value = ta.value.slice(0, ta.selectionStart);
      autosize(ta);
      var next = renderPoint({ text: after, level: level });
      li.after(next);
      focusAt(next.querySelector('textarea'), 0);
      changed();
    } else if (e.key === 'Tab') {
      e.preventDefault();
      var prev = li.previousElementSibling;
      var max = prev ? parseInt(prev.dataset.level, 10) + 1 : 1;
      setLevel(li, e.shiftKey ? level - 1 : Math.min(level + 1, max));
      changed();
    } else if (e.key === 'Backspace' && atStart) {
      if (level > 1) {
        e.preventDefault();
        setLevel(li, level - 1);
        changed();
        return;
      }
      var before = li.previousElementSibling;
      if (!before) return;
      e.preventDefault();
      var pta = before.querySelector('textarea');
      var join = pta.value.length;
      pta.value += (pta.value && ta.value ? ' ' : '') + ta.value;
      li.remove();
      autosize(pta);
      focusAt(pta, join);
      changed();
    } else if (e.key === 'ArrowUp' && atStart && li.previousElementSibling) {
      e.preventDefault();
      focusAt(li.previousElementSibling.querySelector('textarea'), 'end');
    } else if (e.key === 'ArrowDown' && atEnd && li.nextElementSibling) {
      e.preventDefault();
      focusAt(li.nextElementSibling.querySelector('textarea'), 0);
    }
  }
  // Pasting several lines creates several points.
  function onPointPaste(e) {
    var text = (e.clipboardData || window.clipboardData).getData('text');
    if (!text || text.indexOf('\n') === -1) return;
    e.preventDefault();
    var ta = e.target, li = ta.closest('[data-pt]');
    var lines = textToPoints(text);
    if (!lines.length) return;
    var tail = ta.value.slice(ta.selectionEnd);
    ta.value = ta.value.slice(0, ta.selectionStart) + lines[0].text;
    autosize(ta);
    var last = li;
    lines.slice(1).forEach(function (p) {
      var node = renderPoint(p);
      last.after(node);
      last = node;
    });
    var lta = last.querySelector('textarea');
    var pos = lta.value.length;
    lta.value += tail;
    focusAt(lta, pos);
    changed();
  }
  function textToPoints(text) {
    return text.split('\n').map(function (line) {
      var m = line.replace(/\t/g, '  ').match(/^(\s*)(?:[-*•–]+\s*)?(.*)$/);
      var t = (m[2] || '').trim();
      if (!t) return null;
      return { text: t, level: Math.min(3, Math.floor(m[1].length / 2) + 1) };
    }).filter(Boolean);
  }
  function readPoints(sec) {
    return Array.prototype.map.call(sec.querySelectorAll('[data-pt]'), function (li) {
      return { text: li.querySelector('textarea').value.replace(/\s+/g, ' ').trim(), level: parseInt(li.dataset.level, 10) };
    }).filter(function (p) { return p.text; });
  }

  function renderSection(section) {
    var sub = el('input', { value: section.subheading || '', 'aria-label': 'Section title', placeholder: 'Section title', 'data-sub': '', maxlength: '200' });
    var del = el('button', { type: 'button', class: 'icon-btn', 'aria-label': 'Delete section', text: 'Delete' });
    var points = (section.points && section.points.length) ? section.points : [{ text: '', level: 1 }];
    var list = el('ul', { class: 'pts', 'data-points': '' }, points.map(renderPoint));
    var node = el('div', { class: 'sec', 'data-sec': '' }, [el('div', { class: 'sec__head' }, [sub, del]), list]);
    if (section.id) node.dataset.id = section.id;
    del.addEventListener('click', function () {
      var topic = node.closest('[data-topic]');
      node.remove();
      if (!topic.querySelector('[data-sec]')) topic.remove();
      changed();
    });
    // Clicking the empty space under the last point focuses it.
    list.addEventListener('click', function (e) {
      if (e.target === list) focusAt(list.lastElementChild.querySelector('textarea'), 'end');
    });
    return node;
  }

  function topicSections(topic) {
    var heading = topic.querySelector('[data-heading]').value.trim();
    return Array.prototype.map.call(topic.querySelectorAll('[data-sec]'), function (sec) {
      return {
        id: sec.dataset.id ? parseInt(sec.dataset.id, 10) : null,
        heading: heading, subheading: sec.querySelector('[data-sub]').value, points: readPoints(sec)
      };
    });
  }

  function renderTopic(heading, sections) {
    var input = el('input', { value: heading || '', 'aria-label': 'Topic', placeholder: 'Topic', 'data-heading': '', maxlength: '200' });
    var simplify = el('button', { type: 'button', class: 'icon-btn icon-btn--hl', 'data-ai': 'simplify', title: 'Keep only the most important points', text: 'Simplify' });
    var improve = el('button', { type: 'button', class: 'icon-btn', 'data-ai': 'improve', title: 'Tidy up and fill gaps in this topic', text: '✦ Improve' });
    var del = el('button', { type: 'button', class: 'icon-btn', text: 'Delete topic' });
    var body = el('div', { 'data-secs': '' }, sections.map(renderSection));
    var add = el('button', { type: 'button', class: 'icon-btn', text: '+ Add section' });
    var topic = el('section', { class: 'topic', 'data-topic': '' }, [
      el('div', { class: 'topic__head' }, [input, el('div', { class: 'topic__actions' }, [simplify, improve, del])]),
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
    simplify.addEventListener('click', function () { aiTopic(topic, 'simplify').catch(function () {}); });
    improve.addEventListener('click', function () { aiTopic(topic, 'improve').catch(function () {}); });
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

  function hasContent(sec) {
    return readPoints(sec).length || sec.querySelector('[data-sub]').value.trim();
  }

  function collect() {
    var out = [];
    editor.querySelectorAll('[data-topic]').forEach(function (topic) {
      var heading = topic.querySelector('[data-heading]').value.trim() || 'Untitled topic';
      topic.querySelectorAll('[data-sec]').forEach(function (sec) {
        if (!hasContent(sec)) return;
        var sub = sec.querySelector('[data-sub]').value.trim();
        out.push({ id: sec.dataset.id ? parseInt(sec.dataset.id, 10) : null, heading: heading, subheading: sub || heading, points: readPoints(sec) });
      });
    });
    return out;
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
      var withContent = Array.prototype.filter.call(nodes, hasContent);
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

  // ---- AI: simplify / improve (with undo) ---------------------------------
  var AI_LABELS = {
    simplify: { busy: 'Simplifying…', done: 'Simplified to the key points.' },
    improve: { busy: 'Improving…', done: 'Topic improved.' }
  };
  function aiTopic(topic, mode) {
    var heading = topic.querySelector('[data-heading]').value.trim();
    var before = topicSections(topic);
    var sections = before.filter(function (s) { return s.points.length || s.subheading.trim(); });
    if (!sections.length) return Promise.resolve();
    topic.classList.add('is-busy');
    var btn = topic.querySelector('[data-ai="' + mode + '"]');
    var label = btn.textContent;
    btn.textContent = AI_LABELS[mode].busy;
    return QN.request(config.enhance_url, { body: { heading: heading, sections: sections, mode: mode } })
      .then(function (res) {
        var fresh = renderTopic(heading, res.sections);
        var undo = el('button', { type: 'button', class: 'link-btn small', text: 'Undo' });
        var note = el('div', { class: 'topic__note' }, [el('span', { text: AI_LABELS[mode].done + ' ' }), undo]);
        fresh.insertBefore(note, fresh.querySelector('[data-secs]'));
        undo.addEventListener('click', function () {
          fresh.replaceWith(renderTopic(heading, before));
          changed();
        });
        topic.replaceWith(fresh);
        changed();
      })
      .catch(function (err) {
        topic.classList.remove('is-busy');
        btn.textContent = label;
        if (!err.upgrade) QN.toast(err.message, 'error');
        throw err;
      });
  }

  var simplifyAll = document.querySelector('[data-simplify-all]');
  if (simplifyAll) {
    simplifyAll.addEventListener('click', function () {
      var topics = Array.prototype.slice.call(editor.querySelectorAll('[data-topic]'));
      if (!topics.length) return;
      simplifyAll.disabled = true;
      simplifyAll.textContent = 'Simplifying…';
      // One topic at a time keeps each request small and fast.
      topics.reduce(function (chain, t) {
        return chain.then(function () { return aiTopic(t, 'simplify'); });
      }, Promise.resolve()).then(function () {
        QN.toast('Notes simplified. Use Undo on any topic to restore it.');
      }, function () { /* stopped early (limit or error) */ }).then(function () {
        simplifyAll.disabled = false;
        simplifyAll.textContent = 'Simplify all';
      });
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
      if (err.upgrade) return;
      errorEl.textContent = err.message;
      errorEl.hidden = false;
    });
  });

  render(config.sections);
  if (!config.sections.length) document.querySelector('[data-add-topic]').click();
})();
