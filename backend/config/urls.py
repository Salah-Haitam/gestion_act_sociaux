"""URLs racine du projet."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("core.urls")),
    # Interface de login navigable de DRF (pratique pour tester l'API).
    path("api-auth/", include("rest_framework.urls")),
]
