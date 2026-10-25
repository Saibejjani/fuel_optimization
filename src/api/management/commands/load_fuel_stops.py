from api.service import GeoDataHandlingService
import csv
import io
import logging
import requests
import geonamescache
from django.core.management.base import BaseCommand
from api.models import FuelStops

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Load fuel stops from CSV, batch geocode via US Census, and use local fallback'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='CSV file relative path')

    def build_local_city_cache(self):
        """
        Builds an O(1) lookup dictionary for US cities in memory.
        Format: {("austin", "TX"): {"latitude": 30.26715, "longitude": -97.74306}}
        """
        logger.info("Building local city geolocation cache...")
        gc = geonamescache.GeonamesCache(min_city_population=500)
        us_cities = gc.get_cities()
        
        city_index = {}
        for city_id, city_info in us_cities.items():
            if city_info["countrycode"] == "US":
                key = (city_info["name"].strip().lower(), city_info["admin1code"].strip().upper())
                
               
                if key not in city_index:
                    city_index[key] = {
                        "latitude": city_info["latitude"],
                        "longitude": city_info["longitude"]
                    }
        return city_index
    
    def normalize_city_name(city_name):
        city = city_name.strip().lower()
        
        city = city.replace('mt.', 'mount').replace('mt ', 'mount ')
        city = city.replace('st.', 'saint').replace('st ', 'saint ')
        city = city.replace('ft.', 'fort').replace('ft ', 'fort ')
        
        return city

    def handle(self, *args, **kwargs):
        csv_file = kwargs['csv_file']
        
     
        city_cache = self.build_local_city_cache()
        
        opis_data = {}
        batch_csv_content = io.StringIO()
        writer = csv.writer(batch_csv_content)


        with open(csv_file, mode='r', encoding='utf-8-sig') as file:
            reader = csv.DictReader(file)
            for row in reader:
                station_id = row.get('OPIS Truckstop ID')
                opis_data[station_id] = row
                writer.writerow([
                    station_id, 
                    row.get('Address', ''), 
                    row.get('City', ''), 
                    row.get('State', ''), 
                    ""
                ])


        url = 'https://geocoding.geo.census.gov/geocoder/locations/addressbatch'
        payload = {'benchmark': 'Public_AR_Current'}
        files = {'addressFile': ('batch.csv', batch_csv_content.getvalue(), 'text/csv')}

        logger.info("Sending batch to US Census API...")
        response = requests.post(url, data=payload, files=files)

        if response.status_code != 200:
            logger.error(f"Failed to geocode: HTTP {response.status_code}")
            return


        logger.info("Processing results and applying local fallbacks where needed...")
        response_lines = response.text.splitlines()
        result_reader = csv.reader(response_lines)
        stations_to_create = []

        for result_row in result_reader:
            if not result_row or len(result_row) < 3:
                continue

            station_id = result_row[0]
            original_data = opis_data.get(station_id)
            if not original_data:
                continue

            match_status = result_row[2]
            lat, lon = None, None

            if match_status in ('Match', 'Tie') and len(result_row) > 5:
                try:
                    coords = result_row[5].split(',')
                    if len(coords) == 2:
                        lon = float(coords[0].strip())
                        lat = float(coords[1].strip())
                except (ValueError, IndexError):
                    pass

            if lat is None or lon is None:
                city = original_data.get('City', '').strip().lower()
                state = original_data.get('State', '').strip().upper()
                city = self.normalize_city_name(city)
                
                fallback_coords = city_cache.get((city, state))
                if fallback_coords:
                    lat = fallback_coords['latitude']
                    lon = fallback_coords['longitude']
                else:
                    location = f"{city}, {state} USA"
                    try:
                        position = GeoDataHandlingService.get_geo_location_lat_lon(location)
                        lat = position.lat
                        lon = position.lon
                    except:
                        pass
            try:
                raw_price = str(original_data.get('Retail Price', '0.0')).replace('$', '').strip()
                price = float(raw_price or 0.0)
            except ValueError:
                price = 0.0

            stations_to_create.append(
                FuelStops(
                    name=original_data.get('Truckstop Name', 'Unknown'),
                    address=original_data.get('Address', ''),
                    city=original_data.get('City', ''),
                    state=original_data.get('State', ''),
                    price=price,
                    latitude=lat,
                    longitude=lon
                )
            )


        if stations_to_create:
            logger.info(f"Bulk creating {len(stations_to_create)} FuelStops...")
            FuelStops.objects.bulk_create(stations_to_create, batch_size=500)
            logger.info("Loading completed successfully.")
        else:
            logger.warning("No valid stations found to create.")