from utils import haversine
from api.models import FuelStops
from ctypes import cast
from dataclasses import dataclass
from logging import raiseExceptions
import requests
from typing import List, Any, TypedDict

from utils import convert_meter_to_miles

@dataclass
class LatLong:
    lat: float|None
    lon: float|None


class Geometry(TypedDict):
    coordinates: List[List[float]]
    type: str


class Leg(TypedDict):
    steps: List[Any]
    weight: float
    summary: str
    duration: float
    distance: float


class Route(TypedDict):
    legs: List[Leg]
    weight_name: str
    geometry: Geometry
    weight: float
    duration: float
    distance: float

class GeoDataHandlingService:
    SEARCH_URL = "https://nominatim.openstreetmap.org/search?q={location_name}&format=json&limit=1"
    ROUTE_URL = "http://router.project-osrm.org/route/v1/driving/{start_lon},{start_lat};{finish_lon},{finish_lat}?overview=full&geometries=geojson"

    def get_geo_location_lat_lon(self, locaiton: str) -> LatLong :
        headers = {"User-Agent": "DjangoFuelOptimizer/1.0"}
        url = self.SEARCH_URL.format(location_name=locaiton)
        response = requests.get(url, headers=headers)
        if response.status_code == 200 and response.json():
            res = response.json()[0]
            return LatLong(lat=res.get("lat", None), lon=res.get("lon", None))
        raise Exception("location not found")

    def get_route(self, start_position: LatLong, finish_position: LatLong)->Route:
        url = self.ROUTE_URL.format(
            start_lon=start_position.lon,
            start_lat=start_position.lat,
            finish_lat=finish_position.lat,
            finish_lon=finish_position.lon,
        )
        response = requests.get(url)
        if response.status_code == 200 and response.json().get("routes"):
            routes = response.json().get("routes")
            return routes[0]

        raise Exception(f"Route not Found for start_position:{start_position} and finish_position: {finish_position}")


class FuelOptimizationService:
    

    def __init__(self, geo_data_handling_service: GeoDataHandlingService) -> None:
        self.geo_data_handling_service = geo_data_handling_service


    def optimize(self, start_location: str, finish_location: str) -> dict:
        max_range=500
        mpg=10
        stops = []
        total_cost = 0.0
        start_position = self.geo_data_handling_service.get_geo_location_lat_lon(
            start_location
        )
        finish_position = self.geo_data_handling_service.get_geo_location_lat_lon(
            finish_location
        )
        if start_position and finish_position:
            route = self.geo_data_handling_service.get_route(start_position, finish_position)
            distance_in_miles = convert_meter_to_miles(route.get("distance",0))
            positions = route.get("geometry",{}).get("coordinates")

            if distance_in_miles <= max_range:
                    cheapest_station = FuelStops.objects.order_by('price').first()
                    if cheapest_station:
                        total_cost = (distance_in_miles / mpg) * cheapest_station.price
                    return {"stops":stops, "cost":total_cost,"distance": distance_in_miles }

            all_stations = list(FuelStops.objects.all())
            
            miles_covered = 0
            current_fuel_range = max_range
            
            last_point = positions[0]
            
            for i in range(1, len(positions)):
                current_point = positions[i]
                segment_dist = haversine(last_point[1], last_point[0], current_point[1], current_point[0])
                miles_covered += segment_dist
                current_fuel_range -= segment_dist
                
                if current_fuel_range < 100 and (distance_in_miles - miles_covered) > 0:

                    nearby_stations = [
                        s for s in all_stations 
                        if s.latitude and s.longitude and haversine(current_point[1], current_point[0], s.latitude, s.longitude) < 80 
                    ]
                    
                    best_station = min(nearby_stations, key=lambda s: s.price)
                    stops.append({
                        "name": best_station.name,
                        "location": f"{best_station.city}, {best_station.state}",
                        "price": best_station.price
                    })
                    gallons_needed = (max_range - current_fuel_range) / mpg
                    total_cost += gallons_needed * best_station.price
                    current_fuel_range = max_range
                        
                last_point = current_point
            remaining_miles = distance_in_miles - (miles_covered - current_fuel_range)
            if stops and remaining_miles > 0:
                total_cost += (remaining_miles / mpg) * stops[-1]['price']

            return {"stops":stops,"cost":round(total_cost, 2), "distance":round(distance_in_miles, 2)}




if __name__ == "__main__":
    geo_data_service = GeoDataHandlingService()
    data = {"start_location": "New York, NY", "finish_location": "Los Angeles, CA"}
    fuel_optimizaiton = FuelOptimizationService(geo_data_service)
    fuel_optimizaiton.optimize(
        data.get("start_location", ""), data.get("finish_location", "")
    )
