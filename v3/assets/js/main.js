/* ==========================================================================
   Paris Partners Softwares — v3 behaviour
   ---------------------------------------------------------------------------
   Smallest of the three. v3 has no theme toggle (single brand-led look), no
   scroll-reveal and no filtering, so this covers the mobile drawer, the contact
   form and the footer year. Nothing here gates any content.
   ========================================================================== */

(function () {
  "use strict";

  /* ------------------------------------------------------------------- nav */

  function initNav() {
    var toggle = document.querySelector("[data-nav-toggle]");
    var nav = document.getElementById("site-nav");
    if (!toggle || !nav) return;

    function setOpen(open) {
      toggle.setAttribute("aria-expanded", String(open));
      nav.classList.toggle("is-open", open);
      document.body.classList.toggle("is-locked", open);
    }

    toggle.addEventListener("click", function () {
      setOpen(toggle.getAttribute("aria-expanded") !== "true");
    });

    nav.addEventListener("click", function (event) {
      if (event.target.closest("a")) setOpen(false);
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && toggle.getAttribute("aria-expanded") === "true") {
        setOpen(false);
        toggle.focus();
      }
    });

    var wide = window.matchMedia("(min-width: 66.0625rem)");
    var onWide = function (event) {
      if (event.matches) setOpen(false);
    };
    if (wide.addEventListener) wide.addEventListener("change", onWide);
    else wide.addListener(onWide);
  }

  /* ------------------------------------------------------------------ form */
  /* Same contract as v1 and v2: posts JSON to contact.php. Without a
     data-endpoint it validates, then points the visitor at the e-mail address
     rather than pretending to send. */

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

    function validate(input) {
      var field = input.closest(".field");
      if (!field) return input.checkValidity();

      var valid = input.checkValidity();
      var error = field.querySelector(".err");

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

    form.querySelectorAll("input, select, textarea").forEach(function (input) {
      input.addEventListener("blur", function () {
        if (input.value !== "") validate(input);
      });
      input.addEventListener("input", function () {
        var field = input.closest(".field");
        if (field && field.hasAttribute("data-invalid")) validate(input);
      });
    });

    form.addEventListener("submit", function (event) {
      event.preventDefault();

      var honey = form.querySelector('[name="_gotcha"]');
      if (honey && honey.value !== "") return;

      var inputs = Array.prototype.slice.call(form.querySelectorAll("input, select, textarea"));
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
            "Écrivez-nous à contact@parispartners.com ou appelez le 01 56 37 00 00.",
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
          setStatus(
            "Merci, votre message est parti. Nous revenons vers vous sous 24 h ouvrées.",
            "ok"
          );
        })
        .catch(function (error) {
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

  function boot() {
    initNav();
    initForm();
    initYear();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
