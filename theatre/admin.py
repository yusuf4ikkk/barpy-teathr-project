from django.contrib import admin, messages
from django.db.models import Count, Q
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import Actor, Hall, News, Order, Performance, Session, SiteSettings, Ticket, release_expired

STATUS_COLORS = {
    Order.Status.NEW: ("#e3b341", "rgba(227,179,65,.14)"),
    Order.Status.PAID: ("#3fb950", "rgba(63,185,80,.14)"),
    Order.Status.CANCELLED: ("#8b949e", "rgba(139,148,158,.14)"),
    Order.Status.EXPIRED: ("#e0657a", "rgba(224,101,122,.14)"),
}


def thumb(image, size=48, round_=False):
    if not image:
        return "—"
    radius = "50%" if round_ else "8px"
    return format_html(
        '<img src="{}" style="width:{}px;height:{}px;object-fit:cover;border-radius:{};border:1px solid rgba(201,169,98,.35)">',
        image.url, size, size, radius,
    )


# ---------------------------------------------------------------------------
@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Театр", {"fields": ("theatre_name", "tagline", "founded_year")}),
        ("WhatsApp и оплата", {
            "description": "Все заказы с сайта приходят в WhatsApp на указанный номер. Реквизиты и шаблон ответа используются кассиром.",
            "fields": ("whatsapp_number", "payment_instructions", "whatsapp_reply_template", "hold_minutes", "max_seats_per_order"),
        }),
        ("Контакты", {"fields": ("phone", "email", "address", "work_hours", "map_embed_url")}),
        ("Соцсети", {"fields": ("instagram", "telegram", "youtube", "facebook")}),
        ("Страница «О театре»", {"fields": ("about_text", "about_image", "stat_productions", "stat_actors", "stat_audience")}),
        ("Правила посещения", {"fields": ("rules_text",)}),
    )

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        SiteSettings.load()
        return HttpResponseRedirect(reverse("admin:theatre_sitesettings_change", args=[1]))

    def response_change(self, request, obj):
        if "_continue" not in request.POST and "_save" in request.POST:
            self.message_user(request, "Настройки сохранены.", messages.SUCCESS)
            return HttpResponseRedirect(reverse("admin:index"))
        return super().response_change(request, obj)


# ---------------------------------------------------------------------------
@admin.register(Hall)
class HallAdmin(admin.ModelAdmin):
    list_display = ("name", "rows", "seats_per_row", "capacity")


@admin.register(Actor)
class ActorAdmin(admin.ModelAdmin):
    list_display = ("photo_tag", "name", "role", "merit", "position", "is_active")
    list_display_links = ("photo_tag", "name")
    list_editable = ("position", "is_active")
    search_fields = ("name", "role")
    list_filter = ("is_active",)

    @admin.display(description="Фото")
    def photo_tag(self, obj):
        return thumb(obj.photo, 44, True)


class SessionInline(admin.TabularInline):
    model = Session
    extra = 1
    fields = ("starts_at", "hall", "price", "is_active")
    ordering = ("starts_at",)


@admin.register(Performance)
class PerformanceAdmin(admin.ModelAdmin):
    list_display = ("poster_tag", "title", "genre", "status_badge", "age_limit", "next_show", "is_featured", "is_published")
    list_display_links = ("poster_tag", "title")
    list_editable = ("is_featured", "is_published")
    list_filter = ("status", "genre", "is_published", "is_featured")
    search_fields = ("title", "director", "description")
    filter_horizontal = ("cast",)
    inlines = [SessionInline]
    fieldsets = (
        ("Основное", {"fields": ("title", "genre", "status", "age_limit", "duration", "director", "premiere_date")}),
        ("Описание", {"fields": ("description", "cast")}),
        ("Картинки", {"fields": ("poster", "cover"), "description": "Афиша — вертикальная (3:4). Обложка — широкая картинка для главного слайдера."}),
        ("Публикация", {"fields": ("is_published", "is_featured")}),
    )

    @admin.display(description="Афиша")
    def poster_tag(self, obj):
        return thumb(obj.poster, 52)

    @admin.display(description="Статус", ordering="status")
    def status_badge(self, obj):
        color = {"premiere": "#c9a962", "current": "#3fb950", "archive": "#8b949e"}[obj.status]
        return format_html('<b style="color:{}">{}</b>', color, obj.get_status_display())

    @admin.display(description="Ближайший показ")
    def next_show(self, obj):
        s = obj.next_session
        return timezone.localtime(s.starts_at).strftime("%d.%m %H:%M") if s else "—"


# ---------------------------------------------------------------------------
@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ("performance", "starts_local", "hall", "price", "occupancy", "is_active")
    list_editable = ("price", "is_active")
    list_filter = ("is_active", "hall", "performance")
    date_hierarchy = "starts_at"
    search_fields = ("performance__title",)
    autocomplete_fields = ("performance",)

    def get_queryset(self, request):
        release_expired()
        return super().get_queryset(request).select_related("performance", "hall").annotate(
            _sold=Count("tickets", filter=Q(tickets__is_active=True))
        )

    @admin.display(description="Начало", ordering="starts_at")
    def starts_local(self, obj):
        return timezone.localtime(obj.starts_at).strftime("%d.%m.%Y %H:%M")

    @admin.display(description="Продано", ordering="_sold")
    def occupancy(self, obj):
        cap = obj.hall.capacity or 1
        pct = min(100, round(obj._sold * 100 / cap))
        return format_html(
            '<div style="display:flex;align-items:center;gap:10px;min-width:170px">'
            '<div style="flex:1;height:8px;border-radius:8px;background:rgba(255,255,255,.1);overflow:hidden">'
            '<div style="width:{}%;height:100%;background:linear-gradient(90deg,#ecdba8,#c9a962)"></div></div>'
            "<span>{} / {}</span></div>", pct, obj._sold, cap,
        )


# ---------------------------------------------------------------------------
class TicketInline(admin.TabularInline):
    model = Ticket
    extra = 0
    can_delete = False
    fields = ("row", "number", "price", "is_active", "checked_in")
    readonly_fields = ("row", "number", "price", "is_active")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("code", "customer_name", "phone", "show", "seats", "total_sum", "status_badge", "created_local", "chat")
    list_filter = ("status", "session__performance", ("created_at", admin.DateFieldListFilter))
    search_fields = ("code", "customer_name", "phone")
    date_hierarchy = "created_at"
    inlines = [TicketInline]
    actions = ["action_mark_paid", "action_cancel"]
    readonly_fields = ("code", "session", "total", "created_at", "expires_at", "paid_at", "whatsapp_block")
    fieldsets = (
        ("Заказ", {"fields": ("code", "status", "session", "total", "whatsapp_block")}),
        ("Покупатель", {"fields": ("customer_name", "phone")}),
        ("Время", {"fields": ("created_at", "expires_at", "paid_at")}),
        ("Для кассира", {"fields": ("admin_note",)}),
    )

    def get_queryset(self, request):
        release_expired()
        return super().get_queryset(request).select_related("session__performance", "session__hall").prefetch_related("tickets")

    def has_add_permission(self, request):
        return False  # заказы создаются покупателями на сайте

    # --- колонки ---
    @admin.display(description="Спектакль")
    def show(self, obj):
        s = obj.session
        return f"{s.performance.title} · {timezone.localtime(s.starts_at):%d.%m %H:%M}"

    @admin.display(description="Места")
    def seats(self, obj):
        return ", ".join(f"{t.row}/{t.number}" for t in obj.tickets.all())

    @admin.display(description="Сумма", ordering="total")
    def total_sum(self, obj):
        return f"{obj.total} сом"

    @admin.display(description="Создан", ordering="created_at")
    def created_local(self, obj):
        return timezone.localtime(obj.created_at).strftime("%d.%m %H:%M")

    @admin.display(description="Статус", ordering="status")
    def status_badge(self, obj):
        fg, bg = STATUS_COLORS[obj.status]
        return format_html(
            '<span style="display:inline-block;padding:3px 10px;border-radius:999px;font-weight:600;font-size:12px;color:{};background:{}">{}</span>',
            fg, bg, obj.get_status_display(),
        )

    @admin.display(description="WhatsApp")
    def chat(self, obj):
        return format_html(
            '<a href="{}" target="_blank" rel="noopener" style="color:#25d366;font-weight:600">Ответить →</a>',
            obj.customer_whatsapp_url(),
        )

    @admin.display(description="Чат с клиентом")
    def whatsapp_block(self, obj):
        if not obj.pk:
            return "—"
        return format_html(
            '<a class="button" style="background:#25d366;color:#06260f;padding:8px 16px;border-radius:999px;font-weight:700" '
            'href="{}" target="_blank" rel="noopener">Ответить клиенту в WhatsApp (с реквизитами)</a>',
            obj.customer_whatsapp_url(),
        )

    # --- действия ---
    @admin.action(description="✔ Подтвердить оплату (выдать билеты)")
    def action_mark_paid(self, request, queryset):
        ok = 0
        for order in queryset:
            try:
                order.mark_paid()
                ok += 1
            except ValueError as e:
                self.message_user(request, f"{order.code}: {e}", messages.ERROR)
        if ok:
            self.message_user(request, f"Оплата подтверждена: {ok} заказ(ов).", messages.SUCCESS)

    @admin.action(description="✖ Отменить заказ (освободить места)")
    def action_cancel(self, request, queryset):
        n = 0
        for order in queryset.exclude(status=Order.Status.CANCELLED):
            order.cancel()
            n += 1
        self.message_user(request, f"Отменено заказов: {n}. Места снова свободны.", messages.SUCCESS)

    def save_model(self, request, obj, form, change):
        if change and "status" in form.changed_data:
            new = obj.status
            old = Order.objects.get(pk=obj.pk).status
            obj.status = old  # переключаем через методы, чтобы синхронизировать места
            super().save_model(request, obj, form, change)
            try:
                if new == Order.Status.PAID:
                    obj.mark_paid()
                elif new in (Order.Status.CANCELLED, Order.Status.EXPIRED):
                    obj.cancel(new)
                elif new == Order.Status.NEW and old != new:
                    messages.warning(request, "Вернуть заказ в «Ожидает оплаты» нельзя — оформите новый заказ.")
            except ValueError as e:
                messages.error(request, str(e))
            return
        super().save_model(request, obj, form, change)


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("order", "show", "row", "number", "price", "is_active", "checked_in")
    list_filter = ("is_active", "checked_in", "session__performance", "session")
    search_fields = ("order__code", "order__customer_name", "order__phone")
    list_editable = ("checked_in",)
    actions = ["check_in"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("order", "session__performance")

    def has_add_permission(self, request):
        return False

    @admin.display(description="Сеанс")
    def show(self, obj):
        return f"{obj.session.performance.title} · {timezone.localtime(obj.session.starts_at):%d.%m %H:%M}"

    @admin.action(description="Отметить: вошли в зал")
    def check_in(self, request, queryset):
        queryset.update(checked_in=True)


@admin.register(News)
class NewsAdmin(admin.ModelAdmin):
    list_display = ("image_tag", "title", "published_at", "is_published")
    list_display_links = ("image_tag", "title")
    list_editable = ("is_published",)
    search_fields = ("title",)
    date_hierarchy = "published_at"

    @admin.display(description="Фото")
    def image_tag(self, obj):
        return thumb(obj.image, 56)
