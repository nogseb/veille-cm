(function () {
  var root = document.documentElement;
  root.classList.add('js');
  var KEY = 'veille-cm-theme';

  /* Thème : système par défaut, préférence explicite mémorisée si le stockage est disponible. */
  function systemDark() { return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches; }
  function currentDark() {
    var t = root.getAttribute('data-theme');
    return t ? t === 'dark' : systemDark();
  }
  document.querySelectorAll('[data-theme-toggle]').forEach(function (btn) {
    function label() {
      var dark = currentDark();
      btn.setAttribute('aria-label', dark ? 'Passer en mode clair' : 'Passer en mode sombre');
      btn.setAttribute('aria-pressed', dark ? 'true' : 'false');
    }
    btn.setAttribute('data-ready', '');
    label();
    btn.addEventListener('click', function () {
      var next = currentDark() ? 'light' : 'dark';
      root.setAttribute('data-theme', next);
      try { localStorage.setItem(KEY, next); } catch (e) {}
      label();
    });
  });

  /* Vues par ancre (aperçu en page unique uniquement). */
  var views = Array.prototype.slice.call(document.querySelectorAll('[data-view]'));
  if (views.length) {
    var ids = views.map(function (v) { return v.id; });
    var showView = function () {
      var h = (location.hash || '').slice(1);
      var target = h ? document.getElementById(h) : null;
      var view = ids.indexOf(h) > -1 ? h : (target && target.closest('[data-view]') ? target.closest('[data-view]').id : ids[0]);
      views.forEach(function (v) { v.hidden = v.id !== view; });
      document.querySelectorAll('.nav-links a').forEach(function (a) {
        if (a.getAttribute('href') === '#' + view) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
      });
      if (target && ids.indexOf(h) === -1) requestAnimationFrame(function () { target.scrollIntoView({ block: 'start' }); });
      else window.scrollTo(0, 0);
    };
    window.addEventListener('hashchange', showView);
    showView();
  }

  /* Filtres : boutons de légende du radar et puces partagent le même état. */
  document.querySelectorAll('[data-filter-scope]').forEach(function (scope) {
    var controls = scope.querySelectorAll('[data-filter]');
    var items = scope.querySelectorAll('[data-item]');
    var sectors = scope.querySelectorAll('[data-sector]');
    var counter = scope.querySelector('[data-count]');
    var empty = scope.querySelector('[data-empty]');
    var nouns = (scope.getAttribute('data-nouns') || 'signal|signaux').split('|');
    function apply(f) {
      var n = 0;
      controls.forEach(function (c) {
        var on = c.getAttribute('data-filter') === f;
        c.classList.toggle('is-active', on);
        c.setAttribute('aria-pressed', on ? 'true' : 'false');
      });
      items.forEach(function (it) {
        var ok = f === 'all' || it.getAttribute('data-item') === f;
        it.hidden = !ok;
        if (ok) n++;
      });
      sectors.forEach(function (s) { s.classList.toggle('is-on', f !== 'all' && s.getAttribute('data-sector') === f); });
      if (counter) counter.textContent = n + ' ' + (n > 1 ? nouns[1] : nouns[0]);
      if (empty) empty.hidden = n !== 0;
    }
    controls.forEach(function (c) {
      c.addEventListener('click', function () { apply(c.getAttribute('data-filter')); });
    });
  });

  /* Quatre regards : contrôle segmenté, toutes les lectures restent visibles sans JavaScript. */
  document.querySelectorAll('[data-tabs]').forEach(function (box) {
    var tabs = box.querySelectorAll('[role="tab"]');
    var panels = box.querySelectorAll('[role="tabpanel"]');
    function select(i, focus) {
      tabs.forEach(function (t, k) {
        var on = k === i;
        t.setAttribute('aria-selected', on ? 'true' : 'false');
        t.tabIndex = on ? 0 : -1;
        panels[k].hidden = !on;
      });
      if (focus) tabs[i].focus();
    }
    tabs.forEach(function (t, i) {
      t.addEventListener('click', function () { select(i); });
      t.addEventListener('keydown', function (e) {
        var k = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
        if (k) { e.preventDefault(); select((i + k + tabs.length) % tabs.length, true); }
      });
    });
    box.querySelector('[role="tablist"]').hidden = false;
    select(0);
  });
})();
