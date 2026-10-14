from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Театр Барпы"
admin.site.site_title = "Театр Барпы — админка"
admin.site.index_title = "Панель управления"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("theatre.urls")),
]

# Загруженные картинки (афиши, фото). На проде лучше отдавать через nginx.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
