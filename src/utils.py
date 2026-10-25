import math
METERS_PER_MILE = 1609.34
EARTH_RADIUS= 3958.8 

def convert_meter_to_miles(meters: float) -> float:
    return meters / METERS_PER_MILE


def haversine(lat1, lon1, lat2, lon2):
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return EARTH_RADIUS * c