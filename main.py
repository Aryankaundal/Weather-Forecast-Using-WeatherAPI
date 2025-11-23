from flask import Flask, render_template, request
import requests
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()
app = Flask(__name__)

# Put your WeatherAPI key here or set WEATHERAPI_KEY env var
WEATHERAPI_KEY = os.getenv("WEATHER_API")
WEATHERAPI_URL = "http://api.weatherapi.com/v1/forecast.json"

def build_query_from_input(user_input: str) -> str:
    """
    If user typed a plain city name (no comma), force India by appending ",IN".
    If user provided "City, Country" already, use as-is.
    """
    if not user_input:
        return "Delhi, IN"
    user_input = user_input.strip()
    # if user provided "City, Country" or coordinates, leave it alone
    if "," in user_input or any(c.isdigit() for c in user_input):
        return user_input
    # default to India (you can change this behavior)
    return f"{user_input}, IN"

def get_weather_for(city_query: str, days: int = 7):
    """
    Query WeatherAPI forecast endpoint for 'days' forecast.
    Returns a structured dict or None on error.
    """
    params = {
        "key": WEATHERAPI_KEY,
        "q": city_query,
        "days": days,
        "aqi": "no",
        "alerts": "no"
    }

    try:
        resp = requests.get(WEATHERAPI_URL, params=params, timeout=8)
    except requests.RequestException as e:
        print("WeatherAPI request failed:", e)
        return None

    if resp.status_code != 200:
        # helpful debug print
        try:
            print("WeatherAPI error:", resp.status_code, resp.json())
        except Exception:
            print("WeatherAPI error: status", resp.status_code)
        return None

    data = resp.json()

    # Safety checks
    if "location" not in data or "current" not in data or "forecast" not in data:
        print("WeatherAPI missing expected keys:", data.keys())
        return None

    # Location
    location = data["location"]
    city = location.get("name", "")
    country = location.get("country", "")

    # Current
    current = data["current"]

    # Forecast (list of forecastday)
    forecast_days = data.get("forecast", {}).get("forecastday", [])

    # Build daily list matching your template fields:
    daily = []
    for fd in forecast_days[:7]:
        date_ts = fd.get("date")
        # weekday short (Sun, Mon,...)
        try:
            day_label = datetime.strptime(date_ts, "%Y-%m-%d").strftime("%a")
        except Exception:
            day_label = date_ts

        day_info = fd.get("day", {})
        condition = day_info.get("condition", {})
        icon = condition.get("icon", "")
        # make icon absolute (WeatherAPI returns scheme-less or relative path)
        if icon and icon.startswith("//"):
            icon = "https:" + icon
        elif icon and icon.startswith("/"):
            icon = "https://cdn.weatherapi.com" + icon

        daily.append({
            "day": day_label,
            # use max/min as "Day" and "Night" temps in °C
            "temp_day": round(day_info.get("maxtemp_c", 0), 1),
            "temp_night": round(day_info.get("mintemp_c", 0), 1),
            "icon": icon,
            "condition_text": condition.get("text", "")
        })

    # For day/night labels on the right column we'll show today's forecast values (if present)
    today_day_temp = daily[0]["temp_day"] if daily else round(current.get("temp_c", 0), 1)
    today_night_temp = daily[0]["temp_night"] if daily else round(current.get("temp_c", 0), 1)

    # Astro info (sunrise/sunset) usually in forecastday[0].astro
    sunrise = "--"
    sunset = "--"
    if forecast_days:
        astro = forecast_days[0].get("astro", {})
        sunrise = astro.get("sunrise", "--")
        sunset = astro.get("sunset", "--")

    return {
        "city": city,
        "country": country,
        "current": {
            "temp_c": current.get("temp_c"),
            "feelslike_c": current.get("feelslike_c"),
            "humidity": current.get("humidity"),
            "pressure_mb": current.get("pressure_mb"),
            "wind_kph": current.get("wind_kph"),
            "condition_text": current.get("condition", {}).get("text", "")
        },
        "daily": daily,
        "today_day_temp": today_day_temp,
        "today_night_temp": today_night_temp,
        "sunrise": sunrise,
        "sunset": sunset
    }


@app.route("/", methods=["GET"])
def home():
    # get raw user input
    user_city = request.args.get("city", "").strip()
    query = build_query_from_input(user_city)

    # fetch weather (7 days requested)
    data = get_weather_for(query, days=7)

    # if API failed: render with safe fallback (empty forecast, default name)
    if data is None:
        # preserve what user typed for UX
        fallback_city = user_city if user_city else "Delhi, IN"
        return render_template(
            "index.html",
            city=fallback_city.split(",")[0],
            country="--",
            day_temp=0,
            night_temp=0,
            humidity=0,
            pressure=0,
            wind=0,
            sunrise="--",
            sunset="--",
            daily=[]
        )

    # successful
    current = data["current"]
    return render_template(
        "index.html",
        city=data["city"],
        country=data["country"],
        # day/night show today's highs/lows
        day_temp=data["today_day_temp"],
        night_temp=data["today_night_temp"],
        # info glass (from current)
        humidity=current.get("humidity", 0),
        pressure=current.get("pressure_mb", 0),
        wind=current.get("wind_kph", 0),
        sunrise=data.get("sunrise", "--"),
        sunset=data.get("sunset", "--"),
        # render daily list (list of dicts)
        daily=data["daily"]
    )

if __name__ == "__main__":
    app.run(debug=True)
