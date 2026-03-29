import requests
import urllib.parse

# WMO Weather interpretation codes (https://open-meteo.com/en/docs)
WMO_CODES = {
    0: "Clear sky",
    1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    56: "Light freezing drizzle", 57: "Dense freezing drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    66: "Light freezing rain", 67: "Heavy freezing rain",
    71: "Slight snow fall", 73: "Moderate snow fall", 75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail"
}

def get_weather(city: str) -> str:
    """
    Fetches the current weather for a specific city using Open-Meteo API.
    """
    city = city.replace("?", "").replace("!", "").strip()
    if not city:
        return "Please provide a city name."
    
    try:
        # 1. Geocoding API to get latitude and longitude
        safe_city = urllib.parse.quote(city)
        geocode_url = f"https://geocoding-api.open-meteo.com/v1/search?name={safe_city}&count=1"
        geo_r = requests.get(geocode_url, timeout=5)
        geo_r.raise_for_status()
        geo_data = geo_r.json()
        
        if not geo_data.get("results"):
            return f"Could not find coordinates for city: {city}"
            
        location = geo_data["results"][0]
        lat = location["latitude"]
        lon = location["longitude"]
        resolved_name = location.get("name", city)
        
        # 2. Weather API using coordinates
        weather_url = (f"https://api.open-meteo.com/v1/forecast?"
                       f"latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,weather_code")
        
        weather_r = requests.get(weather_url, timeout=5)
        weather_r.raise_for_status()
        weather_data = weather_r.json()
        
        current = weather_data.get("current", {})
        temp_c = current.get("temperature_2m", "?")
        humidity = current.get("relative_humidity_2m", "?")
        wmo_code = current.get("weather_code", 0)
        
        desc = WMO_CODES.get(wmo_code, "Unknown status")
        
        return f"Weather in {resolved_name}: {desc}, {temp_c}°C, Humidity {humidity}%."
        
    except Exception as e:
        return f"Could not fetch weather for {city}. ({e})"


def register(router, tool_map):
    router.add_intent("weather", ["weather in", "weather for", "check weather", "forecast"], lambda t: get_weather(t.replace("weather in","").replace("weather for","").replace("check weather","").replace("forecast","").strip()))
    tool_map.update({ "weather": get_weather })
