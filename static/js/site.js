(function () {
    "use strict";

    // Шапка: фон при прокрутке
    var header = document.getElementById("header");
    function onScroll() { header.classList.toggle("is-scrolled", window.scrollY > 40); }
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });

    // Мобильное меню
    var drawer = document.getElementById("drawer");
    var burger = document.getElementById("burger");
    function setDrawer(open) {
        drawer.classList.toggle("is-open", open);
        drawer.setAttribute("aria-hidden", open ? "false" : "true");
        burger.setAttribute("aria-expanded", open ? "true" : "false");
        document.body.style.overflow = open ? "hidden" : "";
    }
    burger.addEventListener("click", function () { setDrawer(true); });
    document.getElementById("drawerClose").addEventListener("click", function () { setDrawer(false); });
    drawer.querySelectorAll("a").forEach(function (a) { a.addEventListener("click", function () { setDrawer(false); }); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") setDrawer(false); });

    // Появление блоков при прокрутке
    var items = document.querySelectorAll(".reveal");
    if ("IntersectionObserver" in window) {
        var io = new IntersectionObserver(function (entries) {
            entries.forEach(function (en) {
                if (en.isIntersecting) { en.target.classList.add("is-visible"); io.unobserve(en.target); }
            });
        }, { threshold: 0.08, rootMargin: "0px 0px -30px 0px" });
        items.forEach(function (el, i) { el.style.transitionDelay = ((i % 4) * 70) + "ms"; io.observe(el); });
    } else {
        items.forEach(function (el) { el.classList.add("is-visible"); });
    }

    // Слайдер на главной
    var slides = document.querySelectorAll(".hero-slide");
    var dots = document.querySelectorAll(".hero-dots button");
    if (slides.length > 1) {
        var cur = 0, timer;
        var show = function (n) {
            cur = (n + slides.length) % slides.length;
            slides.forEach(function (s, i) { s.classList.toggle("is-active", i === cur); });
            dots.forEach(function (d, i) {
                d.classList.remove("is-active");
                if (i === cur) { void d.offsetWidth; d.classList.add("is-active"); }
            });
        };
        var start = function () { clearInterval(timer); timer = setInterval(function () { show(cur + 1); }, 7000); };
        dots.forEach(function (d, i) { d.addEventListener("click", function () { show(i); start(); }); });
        start();
    }
})();
