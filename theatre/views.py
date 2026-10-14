import re
from datetime import timedelta

from django.contrib import messages
from django.db import IntegrityError, transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET

from .models import Actor, News, Order, Performance, Session, SiteSettings, Ticket, release_expired

MAX_PENDING_PER_PHONE = 3


def _published():
    return Performance.objects.filter(is_published=True)


def home(request):
    now = timezone.now()
    hero = list(_published().filter(is_featured=True).exclude(status="archive")[:4])
    if not hero:
        hero = list(_published().exclude(status="archive")[:3])
    upcoming_ids = (
        Session.objects.filter(is_active=True, starts_at__gte=now, performance__is_published=True)
        .values_list("performance_id", flat=True)
    )
    upcoming = []
    for perf in _published().filter(pk__in=set(upcoming_ids)):
        upcoming.append(perf)
    upcoming.sort(key=lambda p: p.next_session.starts_at if p.next_session else now)
    return render(request, "theatre/home.html", {
        "hero": hero,
        "upcoming": upcoming[:6],
        "news": News.objects.filter(is_published=True)[:3],
    })


def afisha(request):
    status = request.GET.get("status", "current")
    if status not in ("current", "premiere", "archive", "all"):
        status = "current"
    qs = _published()
    if status != "all":
        qs = qs.filter(status=status)
    return render(request, "theatre/afisha.html", {"performances": qs, "status": status})


def performance(request, slug):
    perf = get_object_or_404(_published(), slug=slug)
    sessions = list(perf.upcoming_sessions())
    return render(request, "theatre/performance.html", {
        "perf": perf, "sessions": sessions, "cast": perf.cast.filter(is_active=True),
    })


# ---------------------------------------------------------------------------
# Выбор мест и оформление заказа
# ---------------------------------------------------------------------------

def _normalize_phone(raw):
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 10 and digits.startswith("0"):
        digits = "996" + digits[1:]
    elif len(digits) == 9:
        digits = "996" + digits
    if not 11 <= len(digits) <= 15:
        return None
    return "+" + digits


def _parse_seats(raw_list, hall):
    seats = set()
    for raw in raw_list:
        m = re.fullmatch(r"(\d{1,3})-(\d{1,3})", raw.strip())
        if not m:
            return None
        row, num = int(m.group(1)), int(m.group(2))
        if not (1 <= row <= hall.rows and 1 <= num <= hall.seats_per_row):
            return None
        seats.add((row, num))
    return sorted(seats)


def _build_grid(session, preselected):
    hall = session.hall
    taken = {f"{r}-{n}" for r, n in session.taken_seats()}
    chosen = set(preselected)
    mid = hall.seats_per_row // 2
    grid = []
    for r in range(1, hall.rows + 1):
        row = []
        for n in range(1, hall.seats_per_row + 1):
            key = f"{r}-{n}"
            row.append({
                "key": key, "row": r, "num": n,
                "taken": key in taken,
                "checked": key in chosen and key not in taken,
                "aisle": n == mid and hall.seats_per_row > 6,
            })
        grid.append({"number": r, "seats": row})
    return grid


def seats(request, pk):
    session = get_object_or_404(
        Session.objects.select_related("performance", "hall"), pk=pk, performance__is_published=True
    )
    cfg = SiteSettings.load()
    form = {"name": "", "phone": ""}
    errors = []
    preselected = []

    if request.method == "POST" and session.is_bookable:
        form = {"name": request.POST.get("name", "").strip(), "phone": request.POST.get("phone", "").strip()}
        raw_seats = request.POST.getlist("seat")
        preselected = raw_seats
        if request.POST.get("website"):  # honeypot
            raise Http404()
        parsed = _parse_seats(raw_seats, session.hall)
        phone = _normalize_phone(form["phone"])
        if not parsed:
            errors.append("Выберите хотя бы одно место на схеме.")
        elif len(parsed) > cfg.max_seats_per_order:
            errors.append(f"В одном заказе можно выбрать не более {cfg.max_seats_per_order} мест.")
        if len(form["name"]) < 2:
            errors.append("Укажите ваше имя.")
        if not phone:
            errors.append("Укажите корректный номер телефона, например 0700 123 456.")

        if not errors:
            release_expired()
            pending = Order.objects.filter(phone=phone, status=Order.Status.NEW).count()
            if pending >= MAX_PENDING_PER_PHONE:
                errors.append("У вас уже есть неоплаченные заказы. Оплатите их или дождитесь окончания брони.")
        if not errors:
            try:
                with transaction.atomic():
                    order = Order.objects.create(
                        session=session, customer_name=form["name"][:120], phone=phone,
                        total=len(parsed) * session.price,
                        expires_at=timezone.now() + timedelta(minutes=cfg.hold_minutes),
                    )
                    Ticket.objects.bulk_create([
                        Ticket(order=order, session=session, row=r, number=n, price=session.price)
                        for r, n in parsed
                    ])
                return redirect(order)
            except IntegrityError:
                errors.append("Одно из выбранных мест только что заняли. Выберите другие места.")
                preselected = []
    elif request.method == "POST":
        errors.append("Продажа билетов на этот сеанс закрыта.")

    return render(request, "theatre/seats.html", {
        "session": session,
        "perf": session.performance,
        "hall": session.hall,
        "grid": _build_grid(session, preselected),
        "form": form,
        "errors": errors,
        "max_seats": cfg.max_seats_per_order,
    })


@require_GET
def taken_seats(request, pk):
    session = get_object_or_404(Session, pk=pk)
    return JsonResponse({"taken": [f"{r}-{n}" for r, n in session.taken_seats()]})


def order_detail(request, code):
    release_expired()
    order = get_object_or_404(Order.objects.select_related("session__performance", "session__hall"), code=code)
    return render(request, "theatre/order.html", {
        "order": order,
        "tickets": order.tickets.all(),
        "wa_url": order.whatsapp_url(),
        "seconds_left": max(0, int((order.expires_at - timezone.now()).total_seconds())) if order.status == "new" else 0,
        "fresh": (timezone.now() - order.created_at).total_seconds() < 120,
    })


# ---------------------------------------------------------------------------
# Статические разделы
# ---------------------------------------------------------------------------

def about(request):
    cfg = SiteSettings.load()
    return render(request, "theatre/about.html", {
        "actors": Actor.objects.filter(is_active=True)[:4],
        "years": max(0, timezone.localdate().year - cfg.founded_year),
    })


def troupe(request):
    return render(request, "theatre/troupe.html", {"actors": Actor.objects.filter(is_active=True)})


def news_list(request):
    return render(request, "theatre/news_list.html", {"items": News.objects.filter(is_published=True)})


def news_detail(request, slug):
    item = get_object_or_404(News, slug=slug, is_published=True)
    more = News.objects.filter(is_published=True).exclude(pk=item.pk)[:3]
    return render(request, "theatre/news_detail.html", {"item": item, "more": more})


def contacts(request):
    return render(request, "theatre/contacts.html")


def rules(request):
    return render(request, "theatre/rules.html")
