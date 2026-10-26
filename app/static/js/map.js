/* Quest Map: pixelated road, walking avatar, pin windows with quick actions, trophy victory. */
(function () {
  "use strict";
  var world = document.querySelector("[data-world]");
  if (!world) return;
  var pins = JSON.parse(document.getElementById("pin-data").textContent);
  var meta = JSON.parse(document.getElementById("map-meta").textContent);
  var W = meta.width, H = meta.height;
  var avatar = world.querySelector("[data-avatar]");
  var mode = world.dataset.mode;
  var storeKey = "ht-map-" + world.dataset.key;
  var segEls = Array.prototype.slice.call(world.querySelectorAll("[data-seg]"));
  var DONE = { done: 1, won: 1, missed: 1 };
  var csrf = document.querySelector('meta[name="csrf-token"]').content;
  var walking = false;

  function esc(s) { var d = document.createElement("div"); d.textContent = s == null ? "" : String(s); return d.innerHTML; }
  function save(v) { try { localStorage.setItem(storeKey, String(v)); } catch (e) {} }
  function load() { try { return parseInt(localStorage.getItem(storeKey), 10); } catch (e) { return NaN; } }

  /* ---------- pixelated road on a low-res canvas ---------- */
  function drawRoad() {
    var canvas = world.querySelector("[data-road-canvas]");
    var svg = world.querySelector("[data-road-svg]");
    if (!canvas || typeof Path2D === "undefined" || document.documentElement.classList.contains("simple")) {
      if (canvas) canvas.hidden = true;
      if (svg) svg.style.opacity = 1;
      return;
    }
    var k = 3;
    canvas.width = Math.round(W / k);
    canvas.height = Math.round(H / k);
    var ctx = canvas.getContext("2d");
    var css = getComputedStyle(world);
    var path = new Path2D(canvas.dataset.path);
    ctx.save();
    ctx.scale(1 / k, 1 / k);
    ctx.lineCap = "round";
    [["#1b1022", 50], [css.getPropertyValue("--road-edge").trim() || "#9a9aa6", 44], [css.getPropertyValue("--road").trim() || "#3b3b44", 36]].forEach(function (p) {
      ctx.strokeStyle = p[0]; ctx.lineWidth = p[1]; ctx.stroke(path);
    });
    ctx.setLineDash([12, 15]);
    ctx.lineCap = "butt";
    ctx.strokeStyle = css.getPropertyValue("--road-line").trim() || "#fff";
    ctx.lineWidth = 3.5;
    ctx.stroke(path);
    ctx.restore();
    // snap anti-aliased edges to hard pixels
    try {
      var img = ctx.getImageData(0, 0, canvas.width, canvas.height), d = img.data;
      for (var i = 3; i < d.length; i += 4) d[i] = d[i] < 110 ? 0 : 255;
      ctx.putImageData(img, 0, 0);
    } catch (e) {}
    canvas.hidden = false;
    svg.style.opacity = 0;
  }

  /* ---------- avatar position along the road ---------- */
  // chain: 0 = START, i = pin i-1, pins.length + 1 = trophy
  function chainPoint(i) {
    if (i <= 0) return meta.start;
    if (i <= pins.length) return { x: pins[i - 1].x, y: pins[i - 1].y };
    return { x: meta.trophy.x, y: meta.trophy.y };
  }
  function place(pt) {
    // stand just left of the road centre so the pin underneath stays visible
    avatar.style.left = ((pt.x - 26) / W * 100) + "%";
    avatar.style.top = ((pt.y + 8) / H * 100) + "%";
  }
  function progressIndex() {
    var n = 0;
    while (n < pins.length && DONE[pins[n].state]) n++;
    return n;
  }
  function walk(from, to, done) {
    if (to <= from || HT.reducedMotion()) { place(chainPoint(to)); done && done(); return; }
    walking = true;
    avatar.classList.add("walking");
    var seg = from, len = 0, total = segEls[seg] ? segEls[seg].getTotalLength() : 0, lastX = null;
    var svgSprite = avatar.querySelector("svg");
    function step() {
      len += 7; // move in whole "pixel" steps for a retro feel
      if (len >= total) {
        seg++;
        if (seg >= to || !segEls[seg]) {
          place(chainPoint(to));
          avatar.classList.remove("walking");
          svgSprite.style.transform = "";
          walking = false;
          done && done();
          return;
        }
        len = 0;
        total = segEls[seg].getTotalLength();
      }
      var p = segEls[seg].getPointAtLength(len);
      if (lastX !== null) svgSprite.style.transform = p.x < lastX - .5 ? "scaleX(-1)" : (p.x > lastX + .5 ? "" : svgSprite.style.transform);
      lastX = p.x;
      place(p);
      setTimeout(function () { requestAnimationFrame(step); }, 28);
    }
    step();
  }

  var pos = progressIndex();
  var stored = load();
  if (!isNaN(stored) && stored < pos && stored >= 0) {
    place(chainPoint(stored));
    setTimeout(function () {
      walk(stored, pos, function () { HT.toast("Your avatar walked " + (pos - stored) + " pin" + (pos - stored > 1 ? "s" : "") + " forward!", "success"); });
    }, 500);
  } else {
    place(chainPoint(pos));
  }
  save(pos);
  if (world.getBoundingClientRect().height > innerHeight * 1.2) {
    setTimeout(function () { avatar.scrollIntoView({ block: "center", behavior: HT.reducedMotion() ? "auto" : "smooth" }); }, 250);
  }

  /* ---------- pin state updates ---------- */
  var variants = {};
  var tpl = document.getElementById("pin-variants");
  if (tpl) tpl.content.querySelectorAll("[data-variant]").forEach(function (s) { variants[s.dataset.variant] = s.innerHTML; });
  var VARIANT = { pending: "red", done: "green", won: "gold", locked: "grey", missed: "missed" };

  function relock() {
    if (mode !== "quest") return;
    var seen = false;
    pins.forEach(function (p) {
      if (p.state === "pending" || p.state === "locked") { p.state = seen ? "locked" : "pending"; seen = true; }
    });
  }
  function repaint() {
    relock();
    pins.forEach(function (p, i) {
      var pinBtn = world.querySelector('.pin[data-pin="' + i + '"]');
      var sign = world.querySelector('.sign[data-pin="' + i + '"]');
      if (!pinBtn) return;
      pinBtn.className = "item pin st-" + p.state;
      sign.className = sign.className.replace(/st-\w+/, "st-" + p.state);
      if (p.state !== "pending") sign.className = sign.className.replace(/urg-\w+/, "");
      if (variants[VARIANT[p.state]]) pinBtn.innerHTML = variants[VARIANT[p.state]];
      var c = sign.querySelector(".s-count"); if (c && p.countdown) c.textContent = p.countdown;
    });
    var next = progressIndex();
    var trophy = world.querySelector("[data-trophy]");
    if (mode === "quest") trophy.classList.toggle("ready", next === pins.length);
    if (next > pos && !walking) {
      var from = pos;
      pos = next;
      save(pos);
      walk(from, next, function () {
        if (next === pins.length && mode === "quest") HT.toast("Every pin done! Click the trophy to claim your reward.", "success");
      });
    } else if (next < pos) {
      pos = next; save(pos); place(chainPoint(pos));
    }
  }

  /* ---------- pin windows ---------- */
  function statusSelect(current, id) {
    return '<label class="sr-only" for="' + id + '">Status</label><select id="' + id + '" style="flex:1;min-width:150px">' +
      meta.statuses.map(function (s) { return '<option value="' + s + '"' + (s === current ? " selected" : "") + ">" + esc(meta.labels[s]) + "</option>"; }).join("") + "</select>";
  }
  function checklist(items) {
    if (!items || !items.length) return "";
    return '<ul class="checklist">' + items.map(function (m) {
      return '<li class="' + (m.done ? "done" : "") + '"><input class="px-check" type="checkbox" id="pm' + m.id + '" data-ms="' + m.id + '"' + (m.done ? " checked" : "") + '>' +
        '<label class="t check-row" for="pm' + m.id + '" style="margin:0">' + esc(m.title) + '</label><span class="due">' + esc((m.due || "").slice(5, 16)) + "</span></li>";
    }).join("") + "</ul>";
  }

  function openPin(i) {
    var p = pins[i];
    var html = "";
    if (p.kind === "quest") {
      html += '<div class="row"><span class="status status-' + esc(p.status) + '">' + esc(p.status_label) + '</span><strong class="countdown">' + esc(p.countdown) + "</strong></div>" +
        '<p class="small mt-1">' + esc(p.label) + (p.organizer ? " by " + esc(p.organizer) : "") + " · " + esc(p.team) + " · " + esc(p.mode) + (p.prize ? " · " + esc(p.prize) : "") + "</p>" +
        '<div class="row"><span class="pill pill-pink">Priority ' + p.priority + '</span><span class="pill pill-green">Skill fit ' + p.fit + "%</span>" +
        (p.progress !== null ? '<span class="pill">Plan ' + p.progress + "% done</span>" : "") + "</div>";
      html += p.next && p.next.length ? '<h4 class="mt-2">Next back-plan steps</h4>' + checklist(p.next)
        : '<p class="mt-1 small">' + (p.progress === null ? "No back-plan yet. Generate one on the quest page." : "All back-plan steps done!") + "</p>";
      html += '<h4 class="mt-2">Quick actions</h4><div class="row">' + statusSelect(p.status, "pin-status") + '<button class="btn btn-sm btn-primary" type="button" data-set-status>Save status</button></div>' +
        '<form method="post" action="/quests/' + p.id + '/note" class="row mt-1"><input type="hidden" name="csrf_token" value="' + csrf + '">' +
        '<label class="sr-only" for="pin-note">Add a note</label><input id="pin-note" name="note" placeholder="Add a note..." style="flex:1;min-width:150px" required><button class="btn btn-sm">Add note</button></form>' +
        '<div class="row mt-2"><a class="btn btn-sm" href="' + p.url + '">Details</a><a class="btn btn-sm btn-gold" href="' + p.map_url + '">Quest roadmap</a><a class="btn btn-sm" href="' + p.url + '#inventory">Inventory</a></div>';
    } else if (p.kind === "phase") {
      html += '<p><strong>' + esc(p.label) + "</strong> · due " + esc(p.deadline) + " · " + p.progress + "% done</p>" + checklist(p.children) +
        '<p class="small mt-1">Tick every step to turn this pin green and walk forward.</p>';
    } else {
      html += '<p><strong>' + esc(p.label) + "</strong> · deadline " + esc(p.deadline) + "</p>" +
        '<div class="row"><label class="sr-only" for="round-status">Round result</label><select id="round-status" style="flex:1">' +
        meta.roundStatuses.map(function (s) { return '<option value="' + s + '"' + (s === p.status ? " selected" : "") + ">" + s.charAt(0).toUpperCase() + s.slice(1) + "</option>"; }).join("") +
        '</select><button class="btn btn-sm btn-primary" type="button" data-set-round>Save result</button></div>' +
        '<p class="small mt-1">Cleared or skipped rounds turn green. Failed rounds get a skull.</p>';
    }
    if (p.state === "locked") html = '<p class="pill">Locked: finish the earlier pins first (you can still tick ahead).</p>' + html;
    HT.modal({ title: p.title, html: html, okText: "Close", cancel: false });
    var body = document.querySelector("[data-modal-body]");

    body.querySelectorAll("[data-ms]").forEach(function (box) {
      box.addEventListener("change", function () {
        box.disabled = true;
        HT.post("/quests/milestones/" + box.dataset.ms + "/toggle").then(function (j) {
          box.disabled = false;
          if (!j.ok) { box.checked = !box.checked; return HT.toast("Could not save that step.", "error"); }
          box.closest("li").classList.toggle("done", !!j.done);
          HT.showPopups(j.popups, box);
          var list = p.kind === "phase" ? p.children : p.next;
          list.forEach(function (m) { if (String(m.id) === box.dataset.ms) m.done = j.done; });
          if (p.kind === "phase") {
            var all = p.children.every(function (m) { return m.done; });
            p.progress = Math.round(100 * p.children.filter(function (m) { return m.done; }).length / p.children.length);
            p.state = all ? "done" : (p.state === "done" ? "pending" : p.state);
            p.countdown = all ? "100% done" : p.countdown;
            repaint();
          } else {
            p.progress = j.progress;
          }
        });
      });
    });
    var setStatus = body.querySelector("[data-set-status]");
    setStatus && setStatus.addEventListener("click", function () {
      var value = body.querySelector("#pin-status").value;
      HT.post("/quests/" + p.id + "/status", { status: value }).then(function (j) {
        if (!j.ok) return HT.toast(j.error || "Could not update status", "error");
        p.status = value; p.status_label = j.label; p.state = j.state;
        if (j.state !== "pending") p.countdown = j.label;
        HT.toast(j.message, "success");
        HT._closeModal && HT._closeModal();
        HT.showPopups(j.popups, world.querySelector('.pin[data-pin="' + i + '"]'));
        repaint();
      });
    });
    var setRound = body.querySelector("[data-set-round]");
    setRound && setRound.addEventListener("click", function () {
      var value = body.querySelector("#round-status").value;
      HT.post("/quests/rounds/" + p.id + "/update", { status: value }).then(function (j) {
        if (!j.ok) return HT.toast(j.error || "Could not update round", "error");
        p.status = value;
        p.state = { cleared: "done", skipped: "done", failed: "missed" }[value] || "pending";
        p.countdown = value.charAt(0).toUpperCase() + value.slice(1);
        HT.toast("Round updated: " + p.countdown, "success");
        HT._closeModal && HT._closeModal();
        HT.showPopups(j.popups, world.querySelector('.pin[data-pin="' + i + '"]'));
        repaint();
      });
    });
  }
  world.addEventListener("click", function (e) {
    var b = e.target.closest("[data-pin]");
    if (b && !walking) openPin(parseInt(b.dataset.pin, 10));
  });

  /* ---------- trophy + victory ---------- */
  world.querySelector("[data-trophy]").addEventListener("click", function () {
    if (mode !== "quest") {
      HT.toast("Each quest has its own roadmap with a trophy. Open a pin, then 'Quest roadmap'.", "info");
      return;
    }
    if (progressIndex() < pins.length) {
      HT.toast("The trophy is locked. Finish " + (pins.length - progressIndex()) + " more pin(s) first!", "info");
      return;
    }
    HT.post("/quests/" + world.dataset.opp + "/claim-trophy").then(function (j) {
      if (!j.ok) return HT.toast(j.error || "Not yet!", "error");
      walk(pins.length, pins.length + 1, function () {
        HT.confetti();
        HT.modal({
          title: "QUEST COMPLETE!",
          html: '<div class="celebrate"><p style="font-family:var(--font-display);font-size:.8rem">You reached the trophy!</p>' +
            (j.first ? "<p>+150 XP and the Trophy Hunter badge are yours.</p>" : "<p>You already claimed this trophy, but a victory lap never hurts.</p>") +
            '<p>Log what worked in your Training Log while it is fresh.</p></div>',
          okText: "Victory!", cancel: false
        });
        setTimeout(function () { HT.showPopups(j.popups); }, 600);
      });
    });
  });

  /* ---------- day / night ---------- */
  function syncNight() {
    world.classList.toggle("night", document.documentElement.dataset.theme === "night");
    drawRoad();
  }
  document.addEventListener("ht:theme", syncNight);
  syncNight();
})();
