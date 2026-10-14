from django.contrib.admin.apps import AdminConfig


class TheatreAdminConfig(AdminConfig):
    default_site = "theatre.sites.BarpyAdminSite"
