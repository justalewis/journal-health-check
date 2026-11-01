// Sorting and filtering for the journal table. The table is complete and
// readable without this script; it only adds the column buttons' behaviour.
(function () {
  var table = document.getElementById("journal-table");
  if (!table) return;
  var tbody = table.tBodies[0];
  var heads = table.tHead.rows[0].cells;

  function key(row, i, kind) {
    var cell = row.cells[i];
    var v = cell.getAttribute("data-value");
    if (v === null) v = cell.textContent.trim().toLowerCase();
    return kind === "num" ? parseFloat(v) : v;
  }

  Array.prototype.forEach.call(heads, function (th, i) {
    var btn = th.querySelector("button");
    if (!btn) return;
    btn.addEventListener("click", function () {
      var kind = th.getAttribute("data-sort") || "text";
      var asc = th.getAttribute("aria-sort") !== "ascending";
      Array.prototype.forEach.call(heads, function (h) { h.removeAttribute("aria-sort"); });
      th.setAttribute("aria-sort", asc ? "ascending" : "descending");
      var rows = Array.prototype.slice.call(tbody.rows);
      rows.sort(function (a, b) {
        var x = key(a, i, kind), y = key(b, i, kind);
        if (x < y) return asc ? -1 : 1;
        if (x > y) return asc ? 1 : -1;
        return 0;
      });
      rows.forEach(function (r) { tbody.appendChild(r); });
    });
  });

  var input = document.getElementById("journal-filter");
  var count = document.getElementById("result-count");
  var none = document.getElementById("no-results");
  if (!input) return;
  input.addEventListener("input", function () {
    var q = input.value.trim().toLowerCase();
    var shown = 0;
    Array.prototype.forEach.call(tbody.rows, function (r) {
      var hit = !q || r.getAttribute("data-name").indexOf(q) !== -1;
      r.hidden = !hit;
      if (hit) shown++;
    });
    count.textContent = q ? shown + " of " + tbody.rows.length + " journals" : "";
    none.hidden = shown !== 0;
  });
})();
