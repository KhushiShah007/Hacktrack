/* HackTrack core UI: theme, simple mode, toasts, confirm dialogs, pop-ups, bell, shortcuts. */
(function () {
  "use strict";
  var doc = document.documentElement;
  var csrf = (document.querySelector('meta[name="csrf-token"]') || {}).content || "";

  function store(key, value) {
    try { if (value === undefined) return localStorage.getItem(key); localStorage.setItem(key, value); } catch (e) { return null; }
  }
  function esc(s) { var d = document.createElement("div"); d.textContent = s == null ? "" : String(s); return d.innerHTML; }

  /* ---------- fetch helper (CSRF + JSON) ---------- */
  window.HT = window.HT || {};
  HT.post = function (url, data) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf, "X-Requested-With": "fetch", "Accept": "application/json" },
      body: JSON.stringify(data || {}),
      credentials: "same-origin"
    }).then(function (r) {
      return r.json().catch(function () { return { ok: false, error: "Unexpected response" }; }).then(function (j) {
        if (!r.ok && j.ok === undefined) j.ok = false;
        return j;
      });
    });
  };
  HT.reducedMotion = function () {
    return doc.classList.contains("simple") || (window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches);
  };

  /* ---------- toasts as dialogue boxes ---------- */
  var toastBox = document.querySelector("[data-toasts]");
  var speakers = { success: "QUEST LOG", error: "WARNING", info: "GUIDE", message: "GUIDE" };
  HT.toast = function (msg, kind) {
    if (!toastBox) return;
    kind = kind || "info";
    var t = document.createElement("div");
    t.className = "toast " + kind;
    t.setAttribute("role", kind === "error" ? "alert" : "status");
    t.innerHTML = '<div><span class="who">' + (speakers[kind] || "GUIDE") + '</span>' + esc(msg) + '</div>' +
      '<button type="button" aria-label="Dismiss">▼</button>';
    t.querySelector("button").addEventListener("click", function () { t.remove(); });
    toastBox.appendChild(t);
    setTimeout(function () { t.remove(); }, kind === "error" ? 9000 : 5000);
  };
  try {
    JSON.parse(document.getElementById("flash-data").textContent || "[]").forEach(function (f) { HT.toast(f[1], f[0]); });
  } catch (e) {}

  /* ---------- XP / level / badge pop-ups with pixel confetti ---------- */
  HT.confetti = function () {
    if (HT.reducedMotion()) return;
    var box = document.createElement("div");
    box.className = "confetti";
    var colours = ["#ff4fb4", "#3df58a", "#4fd8ff", "#ffd23f", "#ff8a3d", "#b48cff"];
    for (var i = 0; i < 70; i++) {
      var p = document.createElement("i");
      p.style.left = Math.random() * 100 + "vw";
      p.style.background = colours[i % colours.length];
      p.style.animationDuration = 1.6 + Math.random() * 1.8 + "s";
      p.style.animationDelay = Math.random() * .5 + "s";
      box.appendChild(p);
    }
    document.body.appendChild(box);
    setTimeout(function () { box.remove(); }, 4200);
  };
  HT.xpFloat = function (text, anchor) {
    var el = document.createElement("div");
    el.className = "xp-float";
    el.innerHTML = '<svg viewBox="0 0 8 8" width="20" height="20" shape-rendering="crispEdges" aria-hidden="true"><rect x="2" width="4" height="8" fill="#ffd23f"/><rect y="2" width="8" height="4" fill="#ffd23f"/><rect x="1" y="1" width="6" height="6" fill="#ffd23f"/><rect x="3" y="2" width="1" height="3" fill="#fff6c2"/></svg>' + esc(text);
    var r = anchor && anchor.getBoundingClientRect ? anchor.getBoundingClientRect() : { left: innerWidth / 2, top: innerHeight / 2 };
    el.style.left = Math.max(8, r.left) + "px";
    el.style.top = Math.max(60, r.top - 10) + "px";
    document.body.appendChild(el);
    setTimeout(function () { el.remove(); }, 1500);
  };
  HT.showPopups = function (list, anchor) {
    (list || []).forEach(function (p, i) {
      setTimeout(function () {
        if (p.kind === "xp") { HT.xpFloat(p.text, anchor); return; }
        HT.confetti();
        HT.modal({
          title: p.kind === "level" ? "LEVEL UP!" : "BADGE UNLOCKED!",
          html: '<div class="celebrate"><div class="bob">' + (p.kind === "level" ? trophySvg() : starSvg()) + '</div><h2>' + esc(p.text) + '</h2><p>Keep questing to unlock more.</p></div>',
          okText: "Continue", cancel: false
        });
      }, i * 700);
    });
  };
  function trophySvg() { return '<svg viewBox="0 0 12 12" width="96" height="96" shape-rendering="crispEdges" aria-hidden="true"><rect x="2" y="0" width="8" height="1" fill="#5a3a00"/><rect x="0" y="1" width="12" height="3" fill="#5a3a00"/><rect x="3" y="1" width="6" height="5" fill="#ffd23f"/><rect x="1" y="2" width="1" height="2" fill="#ffd23f"/><rect x="10" y="2" width="1" height="2" fill="#ffd23f"/><rect x="4" y="1" width="1" height="4" fill="#fff6c2"/><rect x="5" y="6" width="2" height="3" fill="#d99a1e"/><rect x="3" y="9" width="6" height="2" fill="#7a4a26"/></svg>'; }
  function starSvg() { return '<svg viewBox="0 0 7 7" width="96" height="96" shape-rendering="crispEdges" aria-hidden="true"><rect x="3" width="1" height="7" fill="#ffd23f"/><rect y="3" width="7" height="1" fill="#ffd23f"/><rect x="2" y="2" width="3" height="3" fill="#ffd23f"/><rect x="3" y="2" width="1" height="3" fill="#fff"/></svg>'; }
  try { HT.showPopups(JSON.parse(document.getElementById("popup-data").textContent || "[]")); } catch (e) {}

  /* ---------- modal (confirm + generic) ---------- */
  var modal = document.querySelector("[data-modal]");
  var lastFocus = null;
  HT.modal = function (opts) {
    if (!modal) return;
    lastFocus = document.activeElement;
    modal.querySelector("#modal-title").textContent = opts.title || "Are you sure?";
    var body = modal.querySelector("[data-modal-body]");
    body.innerHTML = (opts.html || "<p>" + esc(opts.text || "") + "</p>") +
      '<div class="form-actions" style="justify-content:flex-end">' +
      (opts.cancel === false ? "" : '<button type="button" class="btn" data-modal-cancel>Cancel</button>') +
      '<button type="button" class="btn ' + (opts.danger ? "btn-danger" : "btn-primary") + '" data-modal-ok>' + esc(opts.okText || "OK") + '</button></div>';
    modal.hidden = false;
    var ok = body.querySelector("[data-modal-ok]");
    ok.focus();
    function close(result) {
      modal.hidden = true;
      if (lastFocus && lastFocus.focus) lastFocus.focus();
      if (result && opts.onOk) opts.onOk();
      if (!result && opts.onCancel) opts.onCancel();
    }
    ok.onclick = function () { close(true); };
    var cancel = body.querySelector("[data-modal-cancel]");
    if (cancel) cancel.onclick = function () { close(false); };
    modal.querySelector("[data-modal-close]").onclick = function () { close(false); };
    HT._closeModal = function () { close(false); };
  };
  if (modal) modal.addEventListener("click", function (e) { if (e.target === modal) HT._closeModal && HT._closeModal(); });

  // every destructive form/button carries data-confirm
  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (!form.matches("[data-confirm]") || form.dataset.confirmed === "1") return;
    e.preventDefault();
    HT.modal({
      title: form.dataset.confirmTitle || "Are you sure?",
      text: form.dataset.confirm,
      okText: form.dataset.confirmOk || "Yes, do it",
      danger: true,
      onOk: function () { form.dataset.confirmed = "1"; form.requestSubmit ? form.requestSubmit() : form.submit(); }
    });
  }, true);

  /* ---------- theme / simple / CRT toggles ---------- */
  function syncToggles() {
    document.querySelectorAll("[data-theme-toggle]").forEach(function (b) {
      var night = doc.dataset.theme === "night";
      b.setAttribute("aria-label", night ? "Switch to day world" : "Switch to night world");
      b.innerHTML = night
        ? '<svg class="icon" viewBox="0 0 8 8" width="16" height="16" shape-rendering="crispEdges" aria-hidden="true"><path fill="currentColor" d="M0 0h1v1H0zM3 0h1v2H3zM6 0h1v1H6zM1 1h1v1H1zM5 1h1v1H5zM2 2h3v1H2zM0 3h7v1H0zM2 4h3v1H2zM1 5h1v1H1zM3 5h1v2H3zM5 5h1v1H5zM0 6h1v1H0zM6 6h1v1H6z"/></svg>'
        : '<svg class="icon" viewBox="0 0 8 8" width="16" height="16" shape-rendering="crispEdges" aria-hidden="true"><path fill="currentColor" d="M2 0h3v1H2zM1 1h2v1H1zM0 2h2v4H0zM7 5h1v1H7zM1 6h2v1H1zM5 6h2v1H5zM2 7h4v1H2z"/></svg>';
    });
    document.querySelectorAll("[data-simple-toggle]").forEach(function (b) {
      b.setAttribute("aria-pressed", doc.classList.contains("simple") ? "true" : "false");
    });
    document.querySelectorAll("[data-crt-toggle]").forEach(function (b) { b.checked = doc.classList.contains("crt-on"); });
    document.querySelectorAll("[data-simple-check]").forEach(function (b) { b.checked = doc.classList.contains("simple"); });
  }
  document.addEventListener("click", function (e) {
    var t = e.target.closest("[data-theme-toggle]");
    if (t) {
      doc.dataset.theme = doc.dataset.theme === "night" ? "day" : "night";
      store("ht-theme", doc.dataset.theme);
      syncToggles();
      document.dispatchEvent(new CustomEvent("ht:theme"));
    }
    var s = e.target.closest("[data-simple-toggle]");
    if (s) {
      doc.classList.toggle("simple");
      store("ht-simple", doc.classList.contains("simple") ? "1" : "0");
      HT.toast(doc.classList.contains("simple") ? "Simple mode on: pixel effects and animations off." : "Pixel mode on!", "info");
      syncToggles();
    }
  });
  document.addEventListener("change", function (e) {
    if (e.target.matches("[data-crt-toggle]")) { doc.classList.toggle("crt-on", e.target.checked); store("ht-crt", e.target.checked ? "1" : "0"); }
    if (e.target.matches("[data-simple-check]")) { doc.classList.toggle("simple", e.target.checked); store("ht-simple", e.target.checked ? "1" : "0"); syncToggles(); }
    if (e.target.matches("[data-autosubmit]")) { e.target.form && (e.target.form.requestSubmit ? e.target.form.requestSubmit() : e.target.form.submit()); }
  });
  syncToggles();

  /* ---------- notifications bell ---------- */
  var bell = document.querySelector("[data-bell]");
  var dd = document.getElementById("notif-dropdown");
  if (bell && dd) {
    bell.addEventListener("click", function () {
      var open = dd.hidden;
      dd.hidden = !open;
      bell.setAttribute("aria-expanded", open ? "true" : "false");
      if (!open) return;
      var list = dd.querySelector("[data-notif-list]");
      fetch("/notifications.json", { headers: { Accept: "application/json" }, credentials: "same-origin" })
        .then(function (r) { return r.json(); })
        .then(function (rows) {
          list.innerHTML = rows.length ? rows.map(function (n) {
            return '<a class="notif-item ' + (n.is_read ? "" : "unread") + '" href="' + esc(n.link || "/notifications") + '">' + esc(n.message) +
              '<br><span class="muted small">' + esc(n.created_at) + '</span></a>';
          }).join("") : '<p class="center muted">No messages yet. Quiet in the village.</p>';
        })
        .catch(function () { list.innerHTML = '<p class="center">Could not load messages.</p>'; });
    });
    var mark = dd.querySelector("[data-mark-read]");
    mark && mark.addEventListener("click", function () {
      HT.post("/notifications/read").then(function () {
        var c = document.querySelector("[data-bell-count]"); if (c) c.remove();
        dd.querySelectorAll(".unread").forEach(function (n) { n.classList.remove("unread"); });
        HT.toast("All caught up!", "success");
      });
    });
    document.addEventListener("click", function (e) {
      if (!dd.hidden && !dd.contains(e.target) && !bell.contains(e.target)) { dd.hidden = true; bell.setAttribute("aria-expanded", "false"); }
    });
  }

  /* ---------- mobile menu ---------- */
  var sheet = document.getElementById("menu-sheet");
  document.querySelectorAll("[data-menu-toggle]").forEach(function (b) {
    b.addEventListener("click", function () {
      sheet.hidden = !sheet.hidden;
      document.querySelectorAll("[data-menu-toggle]").forEach(function (x) { x.setAttribute("aria-expanded", sheet.hidden ? "false" : "true"); });
      if (!sheet.hidden) { var f = sheet.querySelector("a"); f && f.focus(); }
    });
  });

  /* ---------- copy buttons ---------- */
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-copy]");
    if (!b) return;
    var src = document.querySelector(b.dataset.copy);
    var text = src ? (src.value !== undefined ? src.value : src.innerText) : b.dataset.copyText || "";
    var done = function () { HT.toast("Copied to clipboard!", "success"); };
    if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(text).then(done, fallback);
    else fallback();
    function fallback() {
      var ta = document.createElement("textarea"); ta.value = text; document.body.appendChild(ta); ta.select();
      try { document.execCommand("copy"); done(); } catch (err) { HT.toast("Copy failed. Select the text manually.", "error"); }
      ta.remove();
    }
  });

  /* ---------- keyboard shortcuts ---------- */
  var help = document.querySelector("[data-help]");
  var pendingG = false;
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      if (modal && !modal.hidden) HT._closeModal && HT._closeModal();
      if (help && !help.hidden) help.hidden = true;
      if (dd && !dd.hidden) { dd.hidden = true; bell.focus(); }
      if (sheet && !sheet.hidden) sheet.hidden = true;
      document.dispatchEvent(new CustomEvent("ht:escape"));
      return;
    }
    var tag = (e.target.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea" || tag === "select" || e.target.isContentEditable || e.ctrlKey || e.metaKey || e.altKey) return;
    if (!document.querySelector(".sidebar")) return; // shortcuts only inside the app
    if (pendingG) { pendingG = false; if (e.key === "d") { location.href = "/dashboard"; } return; }
    switch (e.key) {
      case "/": var s = document.querySelector("[data-search]"); if (s) { e.preventDefault(); s.focus(); } break;
      case "n": location.href = "/quests/new"; break;
      case "b": location.href = "/quests/board"; break;
      case "m": location.href = "/map"; break;
      case "p": location.href = "/quests/briefing"; break;
      case "g": pendingG = true; setTimeout(function () { pendingG = false; }, 1200); break;
      case "?": if (help) { help.hidden = false; help.querySelector("button").focus(); } break;
    }
  });
  if (help) {
    help.querySelector("[data-help-close]").addEventListener("click", function () { help.hidden = true; });
    help.addEventListener("click", function (e) { if (e.target === help) help.hidden = true; });
  }

  /* ---------- skeleton loaders: reveal [data-skeleton-for] when target content loads ---------- */
  HT.unskeleton = function (el) { if (el) el.querySelectorAll(".skeleton").forEach(function (s) { s.remove(); }); };

  /* ---------- quest form: show only the selected type's fields ---------- */
  var typeSel = document.querySelector("[data-type-select]");
  if (typeSel) {
    var sync = function () {
      document.querySelectorAll("[data-type-fields]").forEach(function (fs) {
        var on = fs.dataset.typeFields === typeSel.value;
        fs.hidden = !on;
        fs.querySelectorAll("input,select,textarea").forEach(function (i) { i.disabled = !on; });
      });
      var stages = document.querySelector("[data-stage-hint]");
      if (stages && typeSel.selectedOptions[0]) stages.textContent = typeSel.selectedOptions[0].dataset.stages || "";
    };
    typeSel.addEventListener("change", sync);
    sync();
  }

  /* ---------- inline validation: show messages as soon as a field is left ---------- */
  document.querySelectorAll("form[data-validate] [required]").forEach(function (input) {
    input.addEventListener("blur", function () {
      var field = input.closest(".field");
      if (!field) return;
      var err = field.querySelector(".error.live");
      if (!input.checkValidity()) {
        field.classList.add("has-error");
        if (!err) { err = document.createElement("div"); err.className = "error live"; err.setAttribute("role", "alert"); field.appendChild(err); }
        err.textContent = input.validationMessage;
      } else {
        field.classList.remove("has-error");
        if (err) err.remove();
      }
    });
  });

  /* ---------- feed upvotes without reload ---------- */
  document.addEventListener("submit", function (e) {
    var f = e.target;
    if (!f.matches("[data-vote]")) return;
    e.preventDefault();
    HT.post(f.action).then(function (j) {
      if (!j.ok) return HT.toast(j.error || "Vote failed", "error");
      var c = f.querySelector("[data-votes]"); if (c) c.textContent = j.votes;
      f.querySelector("button").setAttribute("aria-pressed", j.voted ? "true" : "false");
      f.querySelector("button").classList.toggle("btn-pink", j.voted);
    });
  });
})();
