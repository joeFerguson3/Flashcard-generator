/* New set: upload a file or paste text. */
(function () {
  'use strict';
  var form = document.querySelector('[data-new-form]');
  if (!form) return;
  var mode = 'upload';
  QN.tabs(form, function (tab) { mode = tab; });

  var drop = form.querySelector('[data-dropzone]');
  var fileInput = form.querySelector('[data-file]');
  var label = form.querySelector('[data-file-label]');
  var errorEl = form.querySelector('[data-error]');
  var overlay = document.querySelector('[data-overlay]');
  var MAX = 30 * 1024 * 1024;

  function showFile() {
    var f = fileInput.files[0];
    drop.classList.toggle('has-file', !!f);
    label.textContent = f ? f.name + ' (' + (f.size / 1048576).toFixed(1) + ' MB)' : 'Drop a file here or browse';
  }
  fileInput.addEventListener('change', showFile);
  ['dragenter', 'dragover'].forEach(function (ev) {
    drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.add('is-over'); });
  });
  ['dragleave', 'drop'].forEach(function (ev) {
    drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.remove('is-over'); });
  });
  drop.addEventListener('drop', function (e) {
    if (e.dataTransfer.files.length) {
      fileInput.files = e.dataTransfer.files;
      showFile();
    }
  });

  function fail(message) {
    errorEl.textContent = message;
    errorEl.hidden = false;
  }

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    errorEl.hidden = true;
    var data = new FormData(form);
    if (mode === 'upload') {
      data.delete('text');
      var f = fileInput.files[0];
      if (!f) return fail('Choose a file to upload, or switch to Paste text.');
      if (f.size > MAX) return fail('That file is over 30MB. Try splitting it into smaller PDFs by topic.');
    } else {
      data.delete('file');
      if ((data.get('text') || '').trim().length < 80) return fail('Paste at least a paragraph of notes.');
    }
    overlay.hidden = false;
    var stop = QN.startLoader(overlay);
    QN.request(form.getAttribute('action'), { body: data })
      .then(function (res) { window.location.href = res.redirect; })
      .catch(function (err) {
        stop();
        overlay.hidden = true;
        fail(err.message);
      });
  });
})();
