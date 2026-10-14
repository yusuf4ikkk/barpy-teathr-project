from django.urls import path

from . import views

app_name = "theatre"

urlpatterns = [
    path("", views.home, name="home"),
    path("afisha/", views.afisha, name="afisha"),
    path("afisha/<slug:slug>/", views.performance, name="performance"),
    path("seans/<int:pk>/", views.seats, name="seats"),
    path("seans/<int:pk>/zanyato.json", views.taken_seats, name="taken_seats"),
    path("zakaz/<str:code>/", views.order_detail, name="order"),
    path("o-teatre/", views.about, name="about"),
    path("truppa/", views.troupe, name="troupe"),
    path("novosti/", views.news_list, name="news"),
    path("novosti/<slug:slug>/", views.news_detail, name="news_detail"),
    path("kontakty/", views.contacts, name="contacts"),
    path("pravila/", views.rules, name="rules"),
]
