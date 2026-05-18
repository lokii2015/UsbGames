(function () {
  var lines = document.querySelectorAll(".reveal-line");
  if (!lines.length) return;

  function settle(el) {
    function doneOnce(e) {
      if (e.target !== el) return;
      if (e.propertyName !== "opacity") return;
      el.classList.add("reveal-settled");
      el.removeEventListener("transitionend", doneOnce);
    }
    el.addEventListener("transitionend", doneOnce);
    setTimeout(function () {
      el.classList.add("reveal-settled");
      el.removeEventListener("transitionend", doneOnce);
    }, 1900);
  }

  function showAll() {
    lines.forEach(function (el) {
      el.classList.add("is-visible");
      el.classList.add("reveal-settled");
    });
  }

  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    showAll();
    return;
  }

  var hooks = Array.prototype.slice.call(
    document.querySelectorAll(".about-reveal-hook")
  );
  if (!hooks.length) {
    var rest = document.querySelectorAll(".reveal-line:not(.reveal-line--lead)");
    var fallbackObs = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("is-visible");
          settle(entry.target);
          fallbackObs.unobserve(entry.target);
        });
      },
      { root: null, rootMargin: "0px 0px -6% 0px", threshold: 0.12 }
    );
    for (var i = 0; i < rest.length; i++) {
      fallbackObs.observe(rest[i]);
    }
    return;
  }

  var idx = 0;
  var obs = new IntersectionObserver(
    function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        var hook = entry.target;
        var p = hook.nextElementSibling;
        if (!p || !p.classList.contains("reveal-line")) return;
        p.classList.add("is-visible");
        settle(p);
        obs.unobserve(hook);
        idx += 1;
        armNext();
      });
    },
    { root: null, rootMargin: "0px 0px -18% 0px", threshold: 0 }
  );

  function armNext() {
    if (idx >= hooks.length) return;
    var h = hooks[idx];
    function go() {
      obs.observe(h);
    }
    var r = h.getBoundingClientRect();
    var vh = window.innerHeight;
    var fullyOutside = r.top > vh || r.bottom < 0;
    if (fullyOutside) {
      requestAnimationFrame(go);
      return;
    }
    var done = false;
    function tryGo() {
      if (done) return;
      done = true;
      window.removeEventListener("wheel", tryGo, wheelOpts);
      clearTimeout(fallbackId);
      requestAnimationFrame(go);
    }
    var wheelOpts = { passive: true };
    window.addEventListener("scroll", tryGo, { passive: true, once: true });
    window.addEventListener("wheel", tryGo, wheelOpts);
    var fallbackId = setTimeout(tryGo, 1400);
  }

  armNext();
})();
