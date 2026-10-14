(function () {
    "use strict";
    // Таймер брони
    var t = document.getElementById("timer");
    if (t) {
        var left = parseInt(t.dataset.seconds, 10) || 0;
        var tick = function () {
            if (left <= 0) { t.textContent = "00:00"; location.reload(); return; }
            var m = Math.floor(left / 60), s = left % 60;
            t.textContent = (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s;
            left -= 1;
            setTimeout(tick, 1000);
        };
        tick();
        // Подхватываем оплату: страница сама обновится, когда кассир подтвердит заказ
        setInterval(function () { if (!document.hidden) location.reload(); }, 45000);
    }

    // Автоматический переход в WhatsApp сразу после оформления (один раз)
    var wa = document.getElementById("waBtn");
    if (wa && wa.dataset.auto === "1") {
        var key = wa.dataset.key, done = false;
        try { done = sessionStorage.getItem(key) === "1"; } catch (e) {}
        if (!done) {
            try { sessionStorage.setItem(key, "1"); } catch (e) {}
            setTimeout(function () { window.location.href = wa.href; }, 1200);
            var note = document.getElementById("waNote");
            if (note) note.textContent = "Открываем WhatsApp… Если ничего не произошло — нажмите кнопку выше.";
        }
    }
})();
