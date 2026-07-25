"""Routage de l'API."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from . import views

router = DefaultRouter()
router.register("personnel", views.PersonnelViewSet, basename="personnel")
router.register("activites", views.ActiviteeViewSet, basename="activitee")
router.register("transactions", views.TransactionViewSet, basename="transaction")

urlpatterns = [
    # Authentification
    path("auth/login/", views.ConnexionView.as_view(), name="login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="refresh"),
    path("auth/verify/", TokenVerifyView.as_view(), name="verify"),
    path("auth/me/", views.profil, name="profil"),
    path("auth/logout/", views.deconnexion, name="logout"),
    # Statistiques
    path("stats/", views.StatistiquesView.as_view(), name="stats"),
    path("stats/couverture/", views.CouvertureView.as_view(), name="couverture"),
    path("stats/rapport-annuel/", views.RapportAnnuelView.as_view(), name="rapport-annuel"),
    # IA
    path("ia/recommandations/", views.RecommandationsView.as_view(), name="recommandations"),
    path(
        "ia/recommandations/export/",
        views.ExportRecommandationsView.as_view(),
        name="recommandations-export",
    ),
    path("ia/clusters/", views.ClustersView.as_view(), name="clusters"),
    path("ia/chatbot/", views.ChatbotView.as_view(), name="chatbot"),
    # CRUD
    path("", include(router.urls)),
]
