import secrets
from urllib.parse import quote

from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def make_slug(model, text, instance=None):
    """Unique slug that also copes with Cyrillic titles."""
    translit = {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z",
        "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
        "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch",
        "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya", "ө": "o", "ү": "u", "ң": "n",
    }
    base = slugify("".join(translit.get(ch, ch) for ch in text.lower())) or "item"
    slug, n = base, 2
    qs = model.objects.all()
    if instance is not None and instance.pk:
        qs = qs.exclude(pk=instance.pk)
    while qs.filter(slug=slug).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug


class SiteSettings(models.Model):
    """Единственная запись с настройками сайта (редактируется в админке)."""

    theatre_name = models.CharField("Название театра", max_length=120, default="Театр Барпы")
    tagline = models.CharField("Слоган", max_length=200, default="Жалал-Абадский областной кыргызский драматический театр имени Барпы Алыкулова")
    founded_year = models.PositiveIntegerField("Год основания", default=1992)

    whatsapp_number = models.CharField(
        "Номер WhatsApp кассы", max_length=20, default="996779949710",
        help_text="Только цифры, с кодом страны, без «+» (например 996700123456). На него придут все заказы.",
    )
    phone = models.CharField("Телефон кассы", max_length=40, default="0779-94-97-10")
    email = models.EmailField("Email", blank=True, default="info@teatr-barpy.kg")
    address = models.CharField("Адрес", max_length=200, default="ул. Эркиндик, 24/5")
    work_hours = models.CharField("Режим работы кассы", max_length=120, default="Пн–Вс: 10:00–19:00")
    map_embed_url = models.TextField(
        "Ссылка для карты (iframe src)", blank=True,
        default="https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3245.938279550886!2d73.00484037612675!3d40.92964732426264!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x38bd15cd079547a3%3A0xa678fb88c7ebc715!2z0JHQsNGA0L_RiyDQotC10LDRgtGAINC40LzQtdC90Lgg0JbQvtGA0L7QtdCy0J4!5e1!3m2!1sru!2sus!4v1772612518183!5m2!1sru!2sus",
        help_text="Google Maps → Поделиться → Встраивание карт → скопируйте адрес из src=\"...\".",
    )
    instagram = models.URLField("Instagram", blank=True)
    telegram = models.URLField("Telegram", blank=True)
    youtube = models.URLField("YouTube", blank=True)
    facebook = models.URLField("Facebook", blank=True)

    hold_minutes = models.PositiveIntegerField(
        "Бронь места, минут", default=30,
        help_text="Сколько минут места удерживаются за клиентом, пока он не оплатил. Затем бронь снимается автоматически.",
    )
    max_seats_per_order = models.PositiveIntegerField("Макс. мест в одном заказе", default=8)
    payment_instructions = models.TextField(
        "Реквизиты для оплаты", blank=True,
        default="Оплата переводом: Элсом / Mbank / О!Деньги — номер 0779 94 97 10 (получатель: Театр Барпы).",
        help_text="Подставляется в сообщение клиенту из админки и показывается на странице заказа.",
    )
    whatsapp_reply_template = models.TextField(
        "Шаблон ответа клиенту в WhatsApp",
        default=(
            "Здравствуйте, {name}! Ваш заказ {code} принят.\n"
            "Спектакль: {title}, {date}\n"
            "Места: {seats}\nСумма: {total} сом\n\n"
            "{payment}\n\nПосле оплаты пришлите, пожалуйста, чек в этот чат — мы вышлем билеты."
        ),
        help_text="Доступны поля: {name} {code} {title} {date} {seats} {total} {payment}. Кнопка «Ответить в WhatsApp» в заказе открывает чат с клиентом с этим текстом.",
    )

    about_text = models.TextField(
        "О театре (текст)",
        default=(
            "Жалал-Абадский областной кыргызский драматический театр имени Барпы Алыкулова создан 13 марта 1992 года в городе Жалал-Абад.\n\n"
            "В 1993 году театру был присвоен областной статус и имя великого акына-импровизатора Барпы Алыкулова, "
            "внёсшего большой вклад в кыргызскую классическую поэзию.\n\n"
            "Сегодня театр представляет разнообразный репертуар — от классики до современной драматургии."
        ),
    )
    about_image = models.ImageField("Фото для раздела «О театре»", upload_to="site/", blank=True)
    stat_productions = models.CharField("Цифра: постановок", max_length=20, default="300+")
    stat_actors = models.CharField("Цифра: артистов", max_length=20, default="45")
    stat_audience = models.CharField("Цифра: зрителей в год", max_length=20, default="50 000+")
    rules_text = models.TextField(
        "Правила посещения",
        default=(
            "Приходите за 30 минут до начала спектакля.\n"
            "Опоздавших зрителей проводят в зал в удобный для спектакля момент.\n"
            "Фото- и видеосъёмка во время спектакля запрещена.\n"
            "Мобильные телефоны необходимо отключить.\n"
            "Возврат билетов возможен не позднее чем за 24 часа до начала спектакля."
        ),
    )

    class Meta:
        verbose_name = "Настройки сайта"
        verbose_name_plural = "Настройки сайта"

    def __str__(self):
        return "Настройки сайта"

    def save(self, *args, **kwargs):
        self.pk = 1
        self.whatsapp_number = "".join(ch for ch in self.whatsapp_number if ch.isdigit())
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def whatsapp_link(self):
        return f"https://wa.me/{self.whatsapp_number}"

    @property
    def rules_list(self):
        return [line.strip() for line in self.rules_text.splitlines() if line.strip()]

    @property
    def about_paragraphs(self):
        return [p.strip() for p in self.about_text.split("\n") if p.strip()]


class Hall(models.Model):
    name = models.CharField("Название зала", max_length=80)
    rows = models.PositiveSmallIntegerField("Рядов", default=8)
    seats_per_row = models.PositiveSmallIntegerField("Мест в ряду", default=12)

    class Meta:
        verbose_name = "Зал"
        verbose_name_plural = "Залы"

    def __str__(self):
        return f"{self.name} ({self.capacity} мест)"

    @property
    def capacity(self):
        return self.rows * self.seats_per_row


class Actor(models.Model):
    name = models.CharField("Имя", max_length=120)
    role = models.CharField("Должность", max_length=120, default="Артист")
    merit = models.CharField("Звание", max_length=120, blank=True, help_text="Например: Заслуженный артист")
    photo = models.ImageField("Фото", upload_to="actors/", blank=True)
    position = models.PositiveIntegerField("Порядок", default=100, help_text="Чем меньше — тем выше в списке")
    is_active = models.BooleanField("Показывать на сайте", default=True)

    class Meta:
        ordering = ["position", "name"]
        verbose_name = "Артист"
        verbose_name_plural = "Труппа"

    def __str__(self):
        return self.name


class Performance(models.Model):
    class Status(models.TextChoices):
        CURRENT = "current", "В репертуаре"
        PREMIERE = "premiere", "Премьера"
        ARCHIVE = "archive", "Архив"

    title = models.CharField("Название", max_length=160)
    slug = models.SlugField(max_length=180, unique=True, blank=True)
    genre = models.CharField("Жанр", max_length=60, default="Драма")
    status = models.CharField("Статус", max_length=10, choices=Status.choices, default=Status.CURRENT)
    poster = models.ImageField("Афиша (вертикальная)", upload_to="posters/", blank=True)
    cover = models.ImageField("Обложка для главной (горизонтальная)", upload_to="covers/", blank=True)
    description = models.TextField("Описание")
    duration = models.CharField("Продолжительность", max_length=40, default="2 ч 00 мин")
    age_limit = models.CharField("Возраст", max_length=10, default="12+")
    director = models.CharField("Режиссёр", max_length=120, blank=True)
    premiere_date = models.DateField("Дата премьеры", null=True, blank=True)
    cast = models.ManyToManyField(Actor, verbose_name="В ролях", blank=True, related_name="performances")
    is_featured = models.BooleanField("Показать на главной (в большом слайдере)", default=False)
    is_published = models.BooleanField("Опубликован", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_featured", "title"]
        verbose_name = "Спектакль"
        verbose_name_plural = "Спектакли"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = make_slug(Performance, self.title, self)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("theatre:performance", args=[self.slug])

    def upcoming_sessions(self):
        return self.sessions.filter(is_active=True, starts_at__gte=timezone.now()).select_related("hall")

    @property
    def next_session(self):
        return self.upcoming_sessions().first()

    @property
    def min_price(self):
        agg = self.upcoming_sessions().aggregate(m=models.Min("price"))
        return agg["m"]


class Session(models.Model):
    performance = models.ForeignKey(Performance, verbose_name="Спектакль", on_delete=models.CASCADE, related_name="sessions")
    hall = models.ForeignKey(Hall, verbose_name="Зал", on_delete=models.PROTECT)
    starts_at = models.DateTimeField("Начало")
    price = models.PositiveIntegerField("Цена билета, сом", default=300)
    is_active = models.BooleanField("Продажа открыта", default=True)

    class Meta:
        ordering = ["starts_at"]
        verbose_name = "Сеанс"
        verbose_name_plural = "Сеансы"

    def __str__(self):
        return f"{self.performance.title} — {timezone.localtime(self.starts_at):%d.%m.%Y %H:%M}"

    @property
    def is_bookable(self):
        return self.is_active and self.starts_at > timezone.now()

    def taken_seats(self):
        release_expired()
        return set(self.tickets.filter(is_active=True).values_list("row", "number"))

    @property
    def sold_count(self):
        release_expired()
        return self.tickets.filter(is_active=True).count()

    @property
    def free_count(self):
        return self.hall.capacity - self.sold_count


class Order(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "Ожидает оплаты"
        PAID = "paid", "Оплачен"
        CANCELLED = "cancelled", "Отменён"
        EXPIRED = "expired", "Бронь истекла"

    code = models.CharField("Номер заказа", max_length=12, unique=True, editable=False)
    session = models.ForeignKey(Session, verbose_name="Сеанс", on_delete=models.PROTECT, related_name="orders")
    customer_name = models.CharField("Имя", max_length=120)
    phone = models.CharField("Телефон", max_length=30)
    status = models.CharField("Статус", max_length=10, choices=Status.choices, default=Status.NEW, db_index=True)
    total = models.PositiveIntegerField("Сумма, сом", default=0)
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    expires_at = models.DateTimeField("Бронь до")
    paid_at = models.DateTimeField("Оплачен", null=True, blank=True)
    admin_note = models.TextField("Заметка кассира", blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"

    def __str__(self):
        return f"{self.code} · {self.customer_name}"

    def save(self, *args, **kwargs):
        if not self.code:
            for _ in range(20):
                code = "BP-" + "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))
                if not Order.objects.filter(code=code).exists():
                    self.code = code
                    break
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("theatre:order", args=[self.code])

    @property
    def active_tickets(self):
        return self.tickets.filter(is_active=True).order_by("row", "number")

    @property
    def seats_text(self):
        return ", ".join(f"ряд {t.row}, место {t.number}" for t in self.tickets.order_by("row", "number"))

    @property
    def is_holding(self):
        return self.status == self.Status.NEW and self.expires_at > timezone.now()

    # --- состояния -------------------------------------------------------
    @transaction.atomic
    def mark_paid(self):
        if self.status == self.Status.PAID:
            return
        if self.status in (self.Status.CANCELLED, self.Status.EXPIRED):
            # места могли быть заняты другим — пробуем вернуть бронь
            seats = list(self.tickets.values_list("row", "number"))
            cond = models.Q(pk__in=[])
            for r, n in seats:
                cond |= models.Q(row=r, number=n)
            clash = Ticket.objects.filter(session=self.session, is_active=True).filter(cond).exists()
            if clash:
                raise ValueError("Часть мест уже занята другим заказом.")
            self.tickets.update(is_active=True)
        self.status = self.Status.PAID
        self.paid_at = timezone.now()
        self.save(update_fields=["status", "paid_at"])

    @transaction.atomic
    def cancel(self, status=None):
        self.status = status or self.Status.CANCELLED
        self.save(update_fields=["status"])
        self.tickets.update(is_active=False)

    # --- WhatsApp --------------------------------------------------------
    def message_to_theatre(self):
        s = self.session
        local = timezone.localtime(s.starts_at)
        lines = [
            f"Здравствуйте! Хочу оформить заказ {self.code}.",
            f"Спектакль: {s.performance.title}",
            f"Дата: {local:%d.%m.%Y}, {local:%H:%M} ({s.hall.name})",
            f"Места: {self.seats_text}",
            f"Сумма: {self.total} сом",
            f"Имя: {self.customer_name}",
            f"Телефон: {self.phone}",
            "Подскажите, пожалуйста, как оплатить.",
        ]
        return "\n".join(lines)

    def whatsapp_url(self):
        number = SiteSettings.load().whatsapp_number
        return f"https://wa.me/{number}?text={quote(self.message_to_theatre())}"

    def reply_text(self):
        cfg = SiteSettings.load()
        s = self.session
        local = timezone.localtime(s.starts_at)
        try:
            return cfg.whatsapp_reply_template.format(
                name=self.customer_name, code=self.code, title=s.performance.title,
                date=f"{local:%d.%m.%Y %H:%M}", seats=self.seats_text, total=self.total,
                payment=cfg.payment_instructions,
            )
        except (KeyError, IndexError, ValueError):
            return cfg.whatsapp_reply_template

    def customer_whatsapp_url(self):
        digits = "".join(ch for ch in self.phone if ch.isdigit())
        if len(digits) == 10 and digits.startswith("0"):  # 0700123456 → 996700123456
            digits = "996" + digits[1:]
        return f"https://wa.me/{digits}?text={quote(self.reply_text())}"


class Ticket(models.Model):
    order = models.ForeignKey(Order, verbose_name="Заказ", on_delete=models.CASCADE, related_name="tickets")
    session = models.ForeignKey(Session, verbose_name="Сеанс", on_delete=models.CASCADE, related_name="tickets")
    row = models.PositiveSmallIntegerField("Ряд")
    number = models.PositiveSmallIntegerField("Место")
    price = models.PositiveIntegerField("Цена", default=0)
    is_active = models.BooleanField("Место занято", default=True)
    checked_in = models.BooleanField("Вошёл в зал", default=False)

    class Meta:
        ordering = ["row", "number"]
        verbose_name = "Билет"
        verbose_name_plural = "Билеты"
        constraints = [
            models.UniqueConstraint(
                fields=["session", "row", "number"],
                condition=models.Q(is_active=True),
                name="unique_active_seat_per_session",
            )
        ]

    def __str__(self):
        return f"Ряд {self.row}, место {self.number}"


def release_expired():
    """Снимает бронь с неоплаченных заказов, у которых вышло время."""
    expired = list(Order.objects.filter(status=Order.Status.NEW, expires_at__lte=timezone.now()).values_list("pk", flat=True))
    if expired:
        with transaction.atomic():
            Order.objects.filter(pk__in=expired, status=Order.Status.NEW).update(status=Order.Status.EXPIRED)
            Ticket.objects.filter(order_id__in=expired).update(is_active=False)


class News(models.Model):
    title = models.CharField("Заголовок", max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    image = models.ImageField("Картинка", upload_to="news/", blank=True)
    excerpt = models.TextField("Краткое описание")
    body = models.TextField("Полный текст", blank=True)
    published_at = models.DateField("Дата", default=timezone.localdate)
    is_published = models.BooleanField("Опубликовано", default=True)

    class Meta:
        ordering = ["-published_at", "-id"]
        verbose_name = "Новость"
        verbose_name_plural = "Новости"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = make_slug(News, self.title, self)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("theatre:news_detail", args=[self.slug])
