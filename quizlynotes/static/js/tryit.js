/* Public "try it" box: paste notes -> quiz without an account. */
(function () {
  'use strict';
  var SAMPLE = 'The human eye detects light using two kinds of photoreceptor in the retina. Rods (about 120 million) ' +
    'are very sensitive to light and are used for night vision, but they do not detect colour. Cones (about 6 million) ' +
    'need brighter light and come in three types, sensitive to short, medium and long wavelengths, which allows colour vision. ' +
    'Cones are concentrated in the fovea, the centre of the retina, which gives the sharpest vision.\n\n' +
    'Signals from the retina travel along the optic nerve to the thalamus and then to the primary visual cortex (V1) ' +
    'at the back of the brain. Hubel and Wiesel discovered that many V1 neurons respond best to lines at a particular ' +
    'orientation. Visual information is organised in retinotopic maps, where neighbouring points in the visual field are ' +
    'processed by neighbouring neurons. Helmholtz described perception as unconscious inference: the brain uses prior ' +
    'knowledge to interpret ambiguous sensory input.';

  document.querySelectorAll('[data-tryit]').forEach(function (root) {
    QN.tabs(root);
    var form = root.querySelector('[data-try-form]');
    var textarea = form.querySelector('textarea');
    var count = root.querySelector('[data-count]');
    var errorEl = root.querySelector('[data-error]');
    var loading = root.querySelector('[data-loading]');

    function updateCount() { count.textContent = textarea.value.length.toLocaleString(); }
    textarea.addEventListener('input', updateCount);
    root.querySelector('[data-sample]').addEventListener('click', function () {
      textarea.value = SAMPLE;
      updateCount();
      textarea.focus();
    });

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      errorEl.hidden = true;
      if (textarea.value.trim().length < 150) {
        errorEl.textContent = 'Paste at least a paragraph of notes (150+ characters), or use the sample.';
        errorEl.hidden = false;
        return;
      }
      loading.hidden = false;
      var stop = QN.startLoader(loading);
      QN.request(form.getAttribute('action'), { body: { text: textarea.value } })
        .then(function (data) { window.location.href = data.redirect; })
        .catch(function (err) {
          stop();
          loading.hidden = true;
          errorEl.textContent = err.status === 429
            ? 'You’ve used the free tries for now. Sign in with Google to keep going, it’s free.'
            : err.message;
          errorEl.hidden = false;
        });
    });
  });
})();
