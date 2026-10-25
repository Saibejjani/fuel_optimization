from django.urls import path

from api.views import  RoutePlannerView

urlpatterns = [
    path("route-planning/", RoutePlannerView.as_view(), name="route-planning"),
]
