from datetime import timedelta

from django.contrib.admin import AdminSite
from django.db.models import Count, Q, Sum
from django.utils import timezone

from .models import Order, Session, SiteSettings, Ticket, release_expired


class BarpyAdminSite(AdminSite):
    """Админка с дашбордом: заказы, выручка, заполняемость ближайших сеансов."""

    site_header = "Театр Барпы"
    site_title = "Театр Барпы — админка"
    index_title = "Панель управления"

    def index(self, request, extra_context=None):
        release_expired()
        now = timezone.now()
        today = timezone.localtime(now).replace(hour=0, minute=0, second=0, microsecond=0)
        paid = Order.objects.filter(status=Order.Status.PAID)

        def revenue(since):
            return paid.filter(paid_at__gte=since).aggregate(s=Sum("total"))["s"] or 0

        upcoming = list(
            Session.objects.filter(starts_at__gte=now, is_active=True)
            .select_related("performance", "hall")
            .annotate(sold=Count("tickets", filter=Q(tickets__is_active=True)))
            .order_by("starts_at")[:6]
        )
        for s in upcoming:
            cap = s.hall.capacity or 1
            s.percent = min(100, round(s.sold * 100 / cap))

        cfg = SiteSettings.load()
        extra_context = {
            **(extra_context or {}),
            "dash": {
                "pending": Order.objects.filter(status=Order.Status.NEW).count(),
                "paid_today": revenue(today),
                "paid_week": revenue(now - timedelta(days=7)),
                "paid_month": revenue(now - timedelta(days=30)),
                "tickets_upcoming": Ticket.objects.filter(is_active=True, session__starts_at__gte=now).count(),
                "upcoming": upcoming,
                "latest": Order.objects.select_related("session__performance")[:8],
                "default_whatsapp": cfg.whatsapp_number == SiteSettings._meta.get_field("whatsapp_number").default,
            },
        }
        return super().index(request, extra_context)
