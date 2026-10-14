from datetime import timedelta
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Hall, Order, Performance, Session, SiteSettings, Ticket


class BaseCase(TestCase):
    def setUp(self):
        cfg = SiteSettings.load()
        cfg.whatsapp_number = "+996 700 111 222"
        cfg.save()
        self.hall = Hall.objects.create(name="Зал", rows=4, seats_per_row=6)
        self.perf = Performance.objects.create(title="Тест Спектакль", description="Описание", is_featured=True)
        self.session = Session.objects.create(
            performance=self.perf, hall=self.hall, price=300, starts_at=timezone.now() + timedelta(days=2)
        )
        self.url = reverse("theatre:seats", args=[self.session.pk])

    def book(self, seats, name="Айбек", phone="0700 123 456", **extra):
        data = {"seat": seats, "name": name, "phone": phone, **extra}
        return self.client.post(self.url, data)


class PublicPagesTests(BaseCase):
    def test_all_pages_open(self):
        for name, args in [
            ("theatre:home", []), ("theatre:afisha", []), ("theatre:about", []), ("theatre:troupe", []),
            ("theatre:news", []), ("theatre:contacts", []), ("theatre:rules", []),
            ("theatre:performance", [self.perf.slug]), ("theatre:seats", [self.session.pk]),
        ]:
            r = self.client.get(reverse(name, args=args))
            self.assertEqual(r.status_code, 200, name)

    def test_slug_generated_from_cyrillic(self):
        self.assertEqual(self.perf.slug, "test-spektakl")

    def test_seat_map_has_all_seats(self):
        r = self.client.get(self.url)
        self.assertContains(r, 'name="seat"', count=24)


class BookingTests(BaseCase):
    def test_booking_creates_order_and_redirects(self):
        r = self.book(["1-1", "1-2"])
        order = Order.objects.get()
        self.assertRedirects(r, order.get_absolute_url())
        self.assertEqual(order.total, 600)
        self.assertEqual(order.phone, "+996700123456")
        self.assertEqual(order.status, Order.Status.NEW)
        self.assertEqual(order.tickets.filter(is_active=True).count(), 2)

    def test_whatsapp_link_contains_number_and_order_details(self):
        self.book(["2-3"])
        order = Order.objects.get()
        url = urlparse(order.whatsapp_url())
        self.assertEqual(url.netloc + url.path, "wa.me/996700111222")
        text = parse_qs(url.query)["text"][0]
        for part in (order.code, "Тест Спектакль", "ряд 2, место 3", "300 сом", "Айбек"):
            self.assertIn(part, text)
        page = self.client.get(order.get_absolute_url())
        self.assertContains(page, "wa.me/996700111222?text=")

    def test_seat_cannot_be_booked_twice(self):
        self.book(["1-1"])
        r = self.book(["1-1", "1-2"], name="Другой", phone="0555 000 111")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "только что заняли")
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(Ticket.objects.filter(is_active=True).count(), 1)

    def test_rejects_bad_input(self):
        for seats, name, phone in [
            ([], "Айбек", "0700123456"),
            (["9-9"], "Айбек", "0700123456"),
            (["abc"], "Айбек", "0700123456"),
            (["1-1"], "", "0700123456"),
            (["1-1"], "Айбек", "123"),
        ]:
            r = self.book(seats, name, phone)
            self.assertEqual(r.status_code, 200)
        self.assertEqual(Order.objects.count(), 0)

    def test_max_seats_limit(self):
        cfg = SiteSettings.load()
        cfg.max_seats_per_order = 2
        cfg.save()
        r = self.book(["1-1", "1-2", "1-3"])
        self.assertContains(r, "не более 2")
        self.assertEqual(Order.objects.count(), 0)

    def test_honeypot(self):
        r = self.book(["1-1"], website="http://spam")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(Order.objects.count(), 0)

    def test_closed_or_past_session_not_bookable(self):
        self.session.starts_at = timezone.now() - timedelta(hours=1)
        self.session.save()
        r = self.book(["1-1"])
        self.assertContains(r, "закрыта")
        self.assertEqual(Order.objects.count(), 0)

    def test_pending_orders_limit_per_phone(self):
        for i in range(3):
            self.book([f"1-{i + 1}"])
        r = self.book(["2-1"])
        self.assertContains(r, "неоплаченные заказы")
        self.assertEqual(Order.objects.count(), 3)


class LifecycleTests(BaseCase):
    def make_order(self, seats=("1-1",)):
        self.book(list(seats))
        return Order.objects.latest("id")

    def test_hold_expires_and_frees_seats(self):
        order = self.make_order()
        Order.objects.filter(pk=order.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
        self.assertEqual(self.session.taken_seats(), set())
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.EXPIRED)
        # место снова можно купить
        r = self.book(["1-1"], phone="0555 111 222")
        self.assertEqual(r.status_code, 302)

    def test_paid_order_keeps_seats_after_expiry_time(self):
        order = self.make_order()
        order.mark_paid()
        Order.objects.filter(pk=order.pk).update(expires_at=timezone.now() - timedelta(hours=5))
        self.assertEqual(self.session.taken_seats(), {(1, 1)})
        page = self.client.get(order.get_absolute_url())
        self.assertContains(page, "Ваши билеты")

    def test_cancel_frees_seats(self):
        order = self.make_order(("3-3", "3-4"))
        order.cancel()
        self.assertEqual(self.session.taken_seats(), set())

    def test_restoring_cancelled_order_fails_if_seat_taken(self):
        order = self.make_order()
        order.cancel()
        self.book(["1-1"], phone="0555 111 222")
        with self.assertRaises(ValueError):
            order.mark_paid()

    def test_customer_whatsapp_reply_url(self):
        order = self.make_order()
        url = order.customer_whatsapp_url()
        self.assertTrue(url.startswith("https://wa.me/996700123456?text="))
        self.assertIn(order.code, parse_qs(urlparse(url).query)["text"][0])

    def test_taken_seats_json(self):
        self.make_order(("2-2",))
        r = self.client.get(reverse("theatre:taken_seats", args=[self.session.pk]))
        self.assertEqual(r.json(), {"taken": ["2-2"]})


class AdminTests(BaseCase):
    def setUp(self):
        super().setUp()
        User = get_user_model()
        User.objects.create_superuser("boss", "b@e.com", "pw12345678")
        self.client.login(username="boss", password="pw12345678")
        self.book(["1-1", "1-2"])
        self.order = Order.objects.get()

    def test_admin_pages_open(self):
        urls = [reverse("admin:index"), reverse("admin:theatre_order_changelist"),
                reverse("admin:theatre_order_change", args=[self.order.pk]),
                reverse("admin:theatre_performance_changelist"), reverse("admin:theatre_performance_add"),
                reverse("admin:theatre_session_changelist"), reverse("admin:theatre_ticket_changelist"),
                reverse("admin:theatre_actor_changelist"), reverse("admin:theatre_news_changelist"),
                reverse("admin:theatre_hall_changelist")]
        for u in urls:
            self.assertEqual(self.client.get(u).status_code, 200, u)
        r = self.client.get(reverse("admin:theatre_sitesettings_changelist"), follow=True)
        self.assertEqual(r.status_code, 200)

    def test_dashboard_shows_stats(self):
        r = self.client.get(reverse("admin:index"))
        self.assertContains(r, "Ждут оплаты")
        self.assertContains(r, self.order.code)

    def test_mark_paid_action(self):
        self.client.post(reverse("admin:theatre_order_changelist"), {
            "action": "action_mark_paid", "_selected_action": [self.order.pk]})
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)
        self.assertIsNotNone(self.order.paid_at)

    def test_cancel_action_frees_seats(self):
        self.client.post(reverse("admin:theatre_order_changelist"), {
            "action": "action_cancel", "_selected_action": [self.order.pk]})
        self.assertEqual(self.session.taken_seats(), set())

    def test_changing_status_in_form_syncs_seats(self):
        url = reverse("admin:theatre_order_change", args=[self.order.pk])
        self.client.post(url, {
            "status": "cancelled", "customer_name": "Айбек", "phone": "+996700123456", "admin_note": "",
            "tickets-TOTAL_FORMS": "2", "tickets-INITIAL_FORMS": "2", "tickets-MIN_NUM_FORMS": "0", "tickets-MAX_NUM_FORMS": "1000",
            "tickets-0-id": self.order.tickets.all()[0].pk, "tickets-0-order": self.order.pk,
            "tickets-1-id": self.order.tickets.all()[1].pk, "tickets-1-order": self.order.pk,
        })
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.CANCELLED)
        self.assertEqual(self.session.taken_seats(), set())

    def test_anonymous_cannot_open_admin(self):
        self.client.logout()
        r = self.client.get(reverse("admin:theatre_order_changelist"))
        self.assertEqual(r.status_code, 302)
