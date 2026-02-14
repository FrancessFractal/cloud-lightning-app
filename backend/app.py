from flask import Flask, jsonify, request
from flask_cors import CORS

from smhi_service import geocode_address, get_monthly_weather_data, get_nearby_stations

app = Flask(__name__)
CORS(app)


@app.route("/api/hello")
def hello():
    return jsonify({"message": "Hello from Python!"})


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


@app.route("/api/weather-data/<station_id>")
def weather_data(station_id):
    """Return monthly cloud coverage and lightning data for a station."""
    try:
        data = get_monthly_weather_data(station_id)
    except Exception as e:
        return jsonify({"error": f"Failed to fetch data: {e}"}), 500

    return jsonify(data)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
