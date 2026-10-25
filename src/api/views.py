from django.views.generic import TemplateView
from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_502_BAD_GATEWAY
from rest_framework.views import APIView, Request, Response

from api.service import (
    FuelOptimizationService,
    GeoDataHandlingService,
)


class RoutePlannerView(APIView):
    service = FuelOptimizationService(GeoDataHandlingService())

    def post(self, request: Request, *args: tuple, **kwargs: dict):
        start_location: str | None = request.data.get("start_location", None)
        finish_location: str | None = request.data.get("finish_location", None)

        if not (start_location and finish_location):
            return Response(
                {"detail": "start_location and finish_location are required"},
                status=HTTP_400_BAD_REQUEST,
            )


        plan = self.service.optimize(start_location, finish_location)


        return Response(plan)
