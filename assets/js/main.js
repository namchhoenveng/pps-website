/* ==========================================================================
   Paris Partners Softwares — site behaviour
   Vanilla ES2020, no dependencies. Replaces the old jQuery + Bootstrap +
   wow.js + isotope + smoothscroll bundle (7 files, ~300 KB) with one module.
   Every feature degrades gracefully if its markup is absent from the page.
   ========================================================================== */

(function () {
  "use strict";

  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  /* ------------------------------------------------------------------ theme */
  /* The inline snippet in <head> sets data-theme before first paint so there
     is no flash. This only handles the toggle and persistence. */

  function initTheme() {
    var toggle = document.querySelector("[data-theme-toggle]");
    if (!toggle) return;

    function currentTheme() {
      var explicit = document.documentElement.getAttribute("data-theme");
      if (explicit) return explicit;
      return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }

    function label() {
      var next = currentTheme() === "dark" ? "clair" : "sombre";
      toggle.setAttribute("aria-label", "Basculer vers le thème " + next);
      toggle.setAttribute("title", "Thème " + next);
    }

    label();

    toggle.addEventListener("click", function () {
      var next = currentTheme() === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      try {
        localStorage.setItem("pps-theme", next);
      } catch (e) {
        /* private browsing — the choice just won't persist */
      }
      label();
    });
  }

  /* --------------------------------------------------------------- nav */

  function initNav() {
    var toggle = document.querySelector("[data-nav-toggle]");
    var nav = document.getElementById("site-nav");
    if (!toggle || !nav) return;

    function setOpen(open) {
      toggle.setAttribute("aria-expanded", String(open));
      nav.classList.toggle("is-open", open);
      document.body.classList.toggle("nav-open", open);
    }

    toggle.addEventListener("click", function () {
      setOpen(toggle.getAttribute("aria-expanded") !== "true");
    });

    /* Close on link activation, Escape, or once the viewport is wide enough
       that the drawer no longer applies. */
    nav.addEventListener("click", function (event) {
      if (event.target.closest("a")) setOpen(false);
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && toggle.getAttribute("aria-expanded") === "true") {
        setOpen(false);
        toggle.focus();
      }
    });

    var wide = window.matchMedia("(min-width: 60.0625rem)");
    var onWide = function (event) {
      if (event.matches) setOpen(false);
    };
    if (wide.addEventListener) wide.addEventListener("change", onWide);
    else wide.addListener(onWide);
  }

  /* ------------------------------------------------------------ sticky head */

  function initHeader() {
    var header = document.querySelector(".site-header");
    if (!header) return;

    var ticking = false;

    function update() {
      header.classList.toggle("is-stuck", window.scrollY > 8);
      ticking = false;
    }

    update();

    window.addEventListener(
      "scroll",
      function () {
        if (ticking) return;
        ticking = true;
        window.requestAnimationFrame(update);
      },
      { passive: true }
    );
  }

  /* ---------------------------------------------------------------- reveal */

  function initReveal() {
    var targets = document.querySelectorAll(".reveal");
    if (!targets.length) return;

    if (reduceMotion.matches || !("IntersectionObserver" in window)) {
      targets.forEach(function (el) {
        el.classList.add("is-visible");
      });
      return;
    }

    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        });
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.08 }
    );

    /* Stagger siblings so grids cascade instead of popping in as a block. */
    targets.forEach(function (el) {
      if (!el.style.getPropertyValue("--reveal-delay")) {
        var siblings = Array.prototype.filter.call(
          el.parentElement ? el.parentElement.children : [],
          function (node) {
            return node.classList.contains("reveal");
          }
        );
        var index = siblings.indexOf(el);
        if (index > 0) {
          el.style.setProperty("--reveal-delay", Math.min(index, 6) * 70 + "ms");
        }
      }
      observer.observe(el);
    });
  }

  /* -------------------------------------------------------------- counters */
  /* Markup: <span data-count-to="4.2" data-suffix="M" data-decimals="1"> */

  function initCounters() {
    var counters = document.querySelectorAll("[data-count-to]");
    if (!counters.length) return;

    function render(el, value) {
      var decimals = parseInt(el.dataset.decimals || "0", 10);
      el.textContent =
        (el.dataset.prefix || "") +
        value.toLocaleString("fr-FR", {
          minimumFractionDigits: decimals,
          maximumFractionDigits: decimals
        }) +
        (el.dataset.suffix || "");
    }

    function run(el) {
      var target = parseFloat(el.dataset.countTo);
      if (isNaN(target)) return;

      if (reduceMotion.matches) {
        render(el, target);
        return;
      }

      var duration = parseInt(el.dataset.duration || "1400", 10);
      var start = null;

      function frame(now) {
        if (start === null) start = now;
        var progress = Math.min((now - start) / duration, 1);
        /* easeOutExpo — fast start, settles precisely on the target */
        var eased = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress);
        render(el, target * eased);
        if (progress < 1) window.requestAnimationFrame(frame);
        else render(el, target);
      }

      window.requestAnimationFrame(frame);
    }

    if (!("IntersectionObserver" in window)) {
      counters.forEach(run);
      return;
    }

    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          run(entry.target);
          observer.unobserve(entry.target);
        });
      },
      { threshold: 0.5 }
    );

    counters.forEach(function (el) {
      render(el, 0);
      observer.observe(el);
    });
  }

  /* ---------------------------------------------------------------- filter */
  /* Replaces jquery.isotope. Filters by a space-separated data-tags list. */

  function initFilter() {
    var group = document.querySelector("[data-filter-group]");
    if (!group) return;

    var buttons = group.querySelectorAll("[data-filter]");
    var listId = group.getAttribute("data-filter-group");
    var list = document.getElementById(listId);
    if (!list || !buttons.length) return;

    var items = list.querySelectorAll("[data-tags]");
    var empty = document.querySelector("[data-filter-empty]");
    var status = document.querySelector("[data-filter-status]");

    function apply(value, announce) {
      var shown = 0;

      items.forEach(function (item) {
        var tags = (item.getAttribute("data-tags") || "").split(/\s+/);
        var match = value === "*" || tags.indexOf(value) !== -1;
        item.hidden = !match;
        if (match) shown++;
      });

      buttons.forEach(function (btn) {
        btn.setAttribute("aria-pressed", String(btn.getAttribute("data-filter") === value));
      });

      if (empty) empty.hidden = shown !== 0;

      /* Only announce in response to a click — announcing the initial state
         would make the page talk over itself on load. */
      if (status && announce) {
        status.textContent =
          shown === 0
            ? "Aucune référence pour ce filtre."
            : shown + (shown > 1 ? " références affichées." : " référence affichée.");
      }
    }

    buttons.forEach(function (btn) {
      btn.addEventListener("click", function () {
        apply(btn.getAttribute("data-filter"), true);
      });
    });

    apply("*", false);
  }

  /* ------------------------------------------------------------------ form */
  /* Static hosting has no mail transport. Set data-endpoint on the <form> to
     your handler (Formspree, Netlify Forms, an internal PHP script…) and this
     posts JSON to it. With no endpoint configured it validates, then points
     the visitor at the mailto: fallback rather than pretending to send. */

  function initForm() {
    var form = document.querySelector("[data-contact-form]");
    if (!form) return;

    var status = form.querySelector("[data-form-status]");

    function setStatus(message, state) {
      if (!status) return;
      status.textContent = message;
      if (state) status.setAttribute("data-state", state);
      else status.removeAttribute("data-state");
    }

    function fieldOf(input) {
      return input.closest(".field");
    }

    function validate(input) {
      var field = fieldOf(input);
      if (!field) return input.checkValidity();

      var valid = input.checkValidity();
      var error = field.querySelector(".error");

      if (valid) {
        field.removeAttribute("data-invalid");
        input.removeAttribute("aria-invalid");
      } else {
        field.setAttribute("data-invalid", "");
        input.setAttribute("aria-invalid", "true");
        if (error) error.textContent = input.validationMessage;
      }
      return valid;
    }

    form.querySelectorAll("input, textarea, select").forEach(function (input) {
      input.addEventListener("blur", function () {
        if (input.value !== "") validate(input);
      });
      input.addEventListener("input", function () {
        var field = fieldOf(input);
        if (field && field.hasAttribute("data-invalid")) validate(input);
      });
    });

    form.addEventListener("submit", function (event) {
      event.preventDefault();

      /* Honeypot: filled means bot. Fail silently — no useful feedback. */
      var honey = form.querySelector('[name="_gotcha"]');
      if (honey && honey.value !== "") return;

      var inputs = Array.prototype.slice.call(
        form.querySelectorAll("input, textarea, select")
      );
      var invalid = inputs.filter(function (input) {
        return !validate(input);
      });

      if (invalid.length) {
        setStatus("Merci de corriger les champs signalés.", "error");
        invalid[0].focus();
        return;
      }

      var endpoint = form.getAttribute("data-endpoint");
      var payload = {};
      new FormData(form).forEach(function (value, key) {
        if (key !== "_gotcha") payload[key] = value;
      });

      if (!endpoint) {
        setStatus(
          "Le formulaire n’est pas encore relié à un serveur d’envoi. " +
            "Écrivez-nous directement à contact@parispartners.com ou appelez le 01 56 37 00 00.",
          "error"
        );
        return;
      }

      var submit = form.querySelector('[type="submit"]');
      if (submit) {
        submit.disabled = true;
        submit.dataset.label = submit.textContent;
        submit.textContent = "Envoi…";
      }
      setStatus("Envoi en cours…");

      fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(payload)
      })
        .then(function (response) {
          /* Read the body either way — the handler returns a useful message
             and, on a 422, the list of fields it rejected. */
          return response
            .json()
            .catch(function () {
              return {};
            })
            .then(function (body) {
              if (!response.ok) {
                var error = new Error(body.error || "HTTP " + response.status);
                error.fields = body.fields;
                throw error;
              }
              return body;
            });
        })
        .then(function () {
          form.reset();
          form.querySelectorAll("[data-invalid]").forEach(function (field) {
            field.removeAttribute("data-invalid");
          });
          setStatus("Merci, votre message est parti. Nous revenons vers vous sous 24 h ouvrées.", "ok");
        })
        .catch(function (error) {
          /* Mark any field the server rejected, so the visitor sees where. */
          if (error && error.fields && error.fields.length) {
            error.fields.forEach(function (name) {
              var input = form.querySelector('[name="' + name + '"]');
              var field = input && input.closest(".field");
              if (field) field.setAttribute("data-invalid", "");
            });
          }

          setStatus(
            (error && error.message ? error.message + " " : "L’envoi a échoué. ") +
              "Vous pouvez nous écrire à contact@parispartners.com ou appeler le 01 56 37 00 00.",
            "error"
          );
        })
        .finally(function () {
          if (submit) {
            submit.disabled = false;
            submit.textContent = submit.dataset.label || "Envoyer";
          }
        });
    });
  }

  /* ------------------------------------------------------------------ year */

  function initYear() {
    document.querySelectorAll("[data-year]").forEach(function (el) {
      el.textContent = String(new Date().getFullYear());
    });
  }

  /* ------------------------------------------------------------------ boot */

  function boot() {
    initTheme();
    initNav();
    initHeader();
    initReveal();
    initCounters();
    initFilter();
    initForm();
    initYear();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
