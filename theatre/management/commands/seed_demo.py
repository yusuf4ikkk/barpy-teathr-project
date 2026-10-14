"""Заполняет сайт демо-данными, чтобы сразу увидеть, как всё выглядит.

    python manage.py seed_demo               # только если база пустая
    python manage.py seed_demo --force       # добавить демо-данные поверх
    python manage.py seed_demo --with-admin  # + создать админа admin / admin12345
"""
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone
from PIL import Image

from theatre.models import Actor, Hall, News, Performance, Session, SiteSettings

SEED_DIR = Path(settings.BASE_DIR) / "seed_images"

ACTORS = [
    ("Александр Петров", "Ведущий артист", "Народный артист"),
    ("Елена Петрова", "Ведущая артистка", "Заслуженная артистка"),
    ("Дмитрий Козлов", "Артист", ""),
    ("Мария Иванова", "Артистка", ""),
    ("Сергей Новиков", "Артист", ""),
    ("Татьяна Морозова", "Артистка", ""),
    ("Павел Васильев", "Артист", ""),
    ("Анна Смирнова", "Артистка", ""),
]

PERFORMANCES = [
    dict(title="Макбет", genre="Трагедия", status="premiere", age="16+", duration="2 ч 30 мин", director="Елена Соколова",
         description="Бессмертная трагедия Уильяма Шекспира в новой интерпретации главного режиссёра театра. Захватывающее представление о власти, честолюбии и судьбе.\nИстория о том, как желание власти может разрушить даже самую благородную душу.",
         cast=[0, 3, 2, 7], featured=True, price=300, img=("barpy-in-3.jpg", "left")),
    dict(title="Вишнёвый сад", genre="Драма", status="current", age="12+", duration="2 ч 45 мин", director="Михаил Волков",
         description="Пьеса Антона Павловича Чехова о прощании с прошлым. История об уходящей дворянской культуре и наступлении новой эпохи.",
         cast=[1, 4, 3], featured=True, price=250, img=("barpy-in.jpg", "center")),
    dict(title="Ревизор", genre="Комедия", status="current", age="12+", duration="2 ч 20 мин", director="Станислав Касьянов",
         description="Сатирическая комедия Николая Гоголя. Остроумная критика чиновничьего произвола и коррупции, не теряющая актуальности уже почти два века.",
         cast=[4, 5, 6], featured=True, price=300, img=("barpy-in.jpg", "right")),
    dict(title="Гамлет", genre="Трагедия", status="current", age="16+", duration="3 ч 00 мин", director="Михаил Волков",
         description="Величайшая трагедия всех времён. История датского принца, вынужденного отомстить за убийство отца.",
         cast=[0, 2, 3], featured=False, price=350, img=("barpy-in-3.jpg", "right")),
    dict(title="Бесприданница", genre="Драма", status="archive", age="14+", duration="2 ч 40 мин", director="Елена Соколова",
         description="Драма Александра Островского о судьбе девушки, не имеющей приданого в обществе, где всё продаётся и покупается.",
         cast=[1, 7], featured=False, price=250, img=("barpy-in-4.jpeg", "center")),
    dict(title="Три сестры", genre="Драма", status="premiere", age="14+", duration="2 ч 50 мин", director="Михаил Волков",
         description="Пьеса Антона Чехова о мечтах, разочарованиях и поиске счастья. История трёх сестёр, мечтающих о Москве.",
         cast=[3, 1, 7], featured=False, price=250, img=("barpy-in-4.jpeg", "left")),
]

NEWS = [
    ("Премьера «Макбета» — уже в этом сезоне", "Приглашаем зрителей на долгожданную премьеру сезона — трагедию Уильяма Шекспира «Макбет» в постановке главного режиссёра Елены Соколовой.", "barpy-in-3.jpg"),
    ("Театр принял участие в театральном фестивале", "Спектакль «Вишнёвый сад» был представлен на престижном театральном фестивале и получил высокую оценку жюри.", "barpy-in.jpg"),
    ("Открыта продажа билетов онлайн", "Теперь выбрать места можно прямо на сайте: оформите заказ и завершите оплату в чате WhatsApp с кассой.", "barpy-in-4.jpeg"),
    ("Детская театральная студия приглашает новичков", "Набор в детскую театральную студию «Кулисы» открыт для детей от 8 до 14 лет.", "barpy-in-2.jpeg"),
    ("Новые лица в труппе театра", "Познакомьтесь с новыми артистами, присоединившимися к нашей труппе в этом сезоне.", "barpy-in.jpg"),
    ("Конкурс на лучшую рецензию", "Напишите рецензию на любой спектакль текущего сезона и получите шанс выиграть годовой абонемент.", "barpy-in-3.jpg"),
]


def crop_file(name, anchor=None, ratio=None, width=900):
    im = Image.open(SEED_DIR / name).convert("RGB")
    if ratio:
        w, h = im.size
        target_w = int(h * ratio)
        if target_w < w:
            x = {"left": 0, "center": (w - target_w) // 2, "right": w - target_w}[anchor or "center"]
            im = im.crop((x, 0, x + target_w, h))
        else:
            target_h = int(w / ratio)
            im = im.crop((0, (h - target_h) // 2, w, (h - target_h) // 2 + target_h))
    if im.width > width:
        im = im.resize((width, int(im.height * width / im.width)), Image.LANCZOS)
    buf = BytesIO()
    im.save(buf, "JPEG", quality=84)
    return ContentFile(buf.getvalue())


class Command(BaseCommand):
    help = "Создаёт демо-контент (спектакли, сеансы, труппу, новости)."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true")
        parser.add_argument("--with-admin", action="store_true", help="создать пользователя admin / admin12345")

    def handle(self, *args, **opts):
        SiteSettings.load()
        if Performance.objects.exists() and not opts["force"]:
            self.stdout.write("В базе уже есть спектакли — пропускаю (используйте --force).")
        else:
            self.seed()
        if opts["with_admin"]:
            User = get_user_model()
            if not User.objects.filter(username="admin").exists():
                User.objects.create_superuser("admin", "admin@example.com", "admin12345")
                self.stdout.write(self.style.WARNING("Создан админ: admin / admin12345 — ОБЯЗАТЕЛЬНО смените пароль!"))

    def seed(self):
        main_hall, _ = Hall.objects.get_or_create(name="Основной зал", defaults=dict(rows=8, seats_per_row=12))
        small_hall, _ = Hall.objects.get_or_create(name="Малый зал", defaults=dict(rows=6, seats_per_row=10))

        actors = []
        for i, (name, role, merit) in enumerate(ACTORS):
            actors.append(Actor.objects.create(name=name, role=role, merit=merit, position=i))

        today = timezone.localdate()
        tz = timezone.get_current_timezone()
        for idx, p in enumerate(PERFORMANCES):
            perf = Performance(
                title=p["title"], genre=p["genre"], status=p["status"], age_limit=p["age"], duration=p["duration"],
                director=p["director"], description=p["description"], is_featured=p["featured"],
                premiere_date=today + timedelta(days=3 + idx) if p["status"] == "premiere" else None,
            )
            name, anchor = p["img"]
            perf.save()
            perf.poster.save(f"{perf.slug}.jpg", crop_file(name, anchor, ratio=3 / 4, width=720), save=False)
            perf.cover.save(f"{perf.slug}-cover.jpg", crop_file(name, None, width=1920), save=False)
            perf.save()
            perf.cast.set([actors[i] for i in p["cast"]])
            if p["status"] != "archive":
                for k in range(3):
                    day = today + timedelta(days=1 + idx + k * 3)
                    hour = 18 if k % 2 else 19
                    Session.objects.create(
                        performance=perf, hall=small_hall if p["price"] <= 250 else main_hall,
                        starts_at=timezone.make_aware(datetime(day.year, day.month, day.day, hour, 0), tz),
                        price=p["price"],
                    )

        for i, (title, excerpt, img) in enumerate(NEWS):
            n = News(title=title, excerpt=excerpt, published_at=today - timedelta(days=i * 4 + 1))
            n.save()
            n.image.save(f"{n.slug}.jpg", crop_file(img, "center", ratio=16 / 10, width=900), save=True)

        cfg = SiteSettings.load()
        cfg.about_image.save("about.jpg", crop_file("barpy-in-2.jpeg", None, width=1200), save=True)
        self.stdout.write(self.style.SUCCESS("Демо-данные созданы."))
