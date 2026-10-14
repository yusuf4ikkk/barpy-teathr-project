(function () {
    "use strict";
    var form = document.getElementById("seatForm");
    if (!form) return;
    var price = parseInt(form.dataset.price, 10) || 0;
    var max = parseInt(form.dataset.max, 10) || 8;
    var picked = document.getElementById("picked");
    var totalEl = document.getElementById("total");
    var btn = document.getElementById("submitBtn");
    var boxes = function () { return Array.prototype.slice.call(form.querySelectorAll('input[name="seat"]')); };

    function fmt(n) { return n.toLocaleString("ru-RU").replace(/ /g, " "); }

    function update() {
        var sel = boxes().filter(function (b) { return b.checked; });
        picked.innerHTML = "";
        if (!sel.length) {
            picked.innerHTML = '<span class="none">Места не выбраны</span>';
        } else {
            sel.sort(function (a, b) { return a.dataset.row - b.dataset.row || a.dataset.num - b.dataset.num; })
               .forEach(function (b) {
                   var chip = document.createElement("span");
                   chip.className = "chip";
                   chip.textContent = "ряд " + b.dataset.row + ", место " + b.dataset.num;
                   picked.appendChild(chip);
               });
        }
        totalEl.textContent = fmt(sel.length * price) + " сом";
    }

    form.addEventListener("change", function (e) {
        if (e.target.name !== "seat") return;
        var count = boxes().filter(function (b) { return b.checked; }).length;
        if (count > max) {
            e.target.checked = false;
            picked.insertAdjacentHTML("afterend", '<div class="alert alert-error" id="maxMsg">В одном заказе — не более ' + max + ' мест.</div>');
            setTimeout(function () { var m = document.getElementById("maxMsg"); if (m) m.remove(); }, 3000);
        }
        update();
    });

    form.addEventListener("submit", function (e) {
        var any = boxes().some(function (b) { return b.checked; });
        if (!any) {
            e.preventDefault();
            picked.innerHTML = '<span class="none" style="color:#ffb9c4">Сначала выберите места на схеме</span>';
            document.getElementById("hall").scrollIntoView({ behavior: "smooth", block: "center" });
            return;
        }
        btn.setAttribute("disabled", "disabled");
        btn.textContent = "Оформляем…";
    });

    // Живое обновление занятых мест (если кто-то купил, пока вы выбираете)
    var url = form.dataset.poll;
    function poll() {
        if (document.hidden || !url) return;
        fetch(url, { headers: { "Accept": "application/json" } })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                var taken = {};
                data.taken.forEach(function (k) { taken[k] = true; });
                boxes().forEach(function (b) {
                    var isTaken = !!taken[b.value];
                    if (isTaken && !b.disabled) { b.checked = false; b.disabled = true; }
                    if (!isTaken && b.disabled) { b.disabled = false; }
                });
                update();
            })
            .catch(function () {});
    }
    setInterval(poll, 15000);
    update();
})();
