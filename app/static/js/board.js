/* Kanban: native HTML5 drag and drop plus a keyboard-friendly status <select> on each card. */
(function () {
  "use strict";
  var board = document.querySelector("[data-kanban]");
  if (!board) return;
  var dragged = null;

  function refreshCounts() {
    board.querySelectorAll(".kanban-col").forEach(function (col) {
      var list = col.querySelector(".kanban-list");
      var n = list.querySelectorAll(".kanban-card").length;
      col.querySelector("[data-count]").textContent = n;
      var empty = list.querySelector("[data-empty]");
      if (n === 0 && !empty) {
        empty = document.createElement("p"); empty.className = "kanban-empty"; empty.dataset.empty = ""; empty.textContent = "Drop a quest here";
        list.appendChild(empty);
      } else if (n > 0 && empty) { empty.remove(); }
    });
  }

  function move(card, status, fromList) {
    var target = board.querySelector('.kanban-list[data-status="' + status + '"]');
    if (!target) return;
    target.prepend(card);
    card.querySelector("[data-board-select]").value = status;
    refreshCounts();
    HT.post("/quests/" + card.dataset.id + "/status", { status: status }).then(function (j) {
      if (!j.ok) {
        HT.toast(j.error || "Could not move that quest.", "error");
        if (fromList) { fromList.prepend(card); card.querySelector("[data-board-select]").value = fromList.dataset.status; refreshCounts(); }
        return;
      }
      HT.toast(j.message, "success");
      HT.showPopups(j.popups, card);
    });
  }

  board.addEventListener("dragstart", function (e) {
    var card = e.target.closest(".kanban-card");
    if (!card) return;
    dragged = card;
    card.classList.add("dragging");
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", card.dataset.id);
  });
  board.addEventListener("dragend", function () {
    if (dragged) dragged.classList.remove("dragging");
    board.querySelectorAll(".drag-over").forEach(function (l) { l.classList.remove("drag-over"); });
    dragged = null;
  });
  board.querySelectorAll(".kanban-list").forEach(function (list) {
    list.addEventListener("dragover", function (e) { e.preventDefault(); list.classList.add("drag-over"); });
    list.addEventListener("dragleave", function (e) { if (!list.contains(e.relatedTarget)) list.classList.remove("drag-over"); });
    list.addEventListener("drop", function (e) {
      e.preventDefault();
      list.classList.remove("drag-over");
      if (!dragged) return;
      var from = dragged.closest(".kanban-list");
      if (from === list) return;
      move(dragged, list.dataset.status, from);
    });
  });
  board.addEventListener("change", function (e) {
    if (!e.target.matches("[data-board-select]")) return;
    var card = e.target.closest(".kanban-card");
    var from = card.closest(".kanban-list");
    move(card, e.target.value, from);
    e.target.focus();
  });
})();
