from flask import Flask, jsonify, request
from flask_cors import CORS

from geocoding import autocomplete_address, geocode_address
from stations import get_all_stations, get_nearby_stations
from weather import get_location_weather, get_station_weather_data

app = Flask(__name__)
CORS(app)


@app.route("/api/hello")
def hello():
    return jsonify({"message": "Hello from Python!"})


@app.route("/api/autocomplete")
def autocomplete():
    """Return place suggestions for a partial address query."""
    q = request.args.get("q", "").strip()
    if len(q) < 3:
        return jsonify({"suggestions": []})
    try:
        results = autocomplete_address(q)
    except Exception:
        results = []
    return jsonify({"suggestions": results})


@app.route("/api/search")
def search():
    """Geocode an address query and return coordinates."""
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "Missing query parameter 'q'"}), 400

    result = geocode_address(query)
    if result is None:
        return jsonify({"error": "No results found for that address"}), 404

    return jsonify(result)


@app.route("/api/stations")
def stations():
    """Return the nearest SMHI stations to a given lat/lng."""
    try:
        lat = float(request.args["lat"])
        lng = float(request.args["lng"])
    except (KeyError, ValueError):
        return jsonify({"error": "Missing or invalid 'lat' and 'lng' parameters"}), 400

    nearby = get_nearby_stations(lat, lng)
    return jsonify({"stations": nearby})


@app.route("/api/all-stations")
def all_stations():
    """Return all active SMHI stations with parameter availability."""
    try:
        data = get_all_stations()
    except Exception as e:
        return jsonify({"error": f"Failed to fetch stations: {e}"}), 500

    return jsonify({"stations": data})


@app.route("/api/location-weather")
def location_weather():
    """Return blended weather data for an exact lat/lng using nearby stations."""
    try:
        lat = float(request.args["lat"])
        lng = float(request.args["lng"])
    except (KeyError, ValueError):
        return jsonify({"error": "Missing or invalid 'lat' and 'lng' parameters"}), 400

    resolution = request.args.get("resolution", "month")
    if resolution not in ("day", "month", "year"):
        resolution = "month"

    try:
        data = get_location_weather(lat, lng, resolution=resolution)
    except Exception as e:
        return jsonify({"error": f"Failed to compute location weather: {e}"}), 500

    return jsonify(data)


@app.route("/api/weather-data/<station_id>")
def weather_data(station_id):
    """Return cloud coverage and lightning data for a station."""
    resolution = request.args.get("resolution", "month")
    if resolution not in ("day", "month", "year"):
        resolution = "month"

    try:
        data = get_station_weather_data(station_id, resolution=resolution)
    except Exception as e:
        return jsonify({"error": f"Failed to fetch data: {e}"}), 500

    return jsonify(data)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
