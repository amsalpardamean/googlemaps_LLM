from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os
import requests
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS

# Load environment variables
load_dotenv()


app = Flask(__name__)
CORS(app)  # Allow integration with Open WebUI if needed

# --- Security Configuration ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY_DATA")
API_ACCESS_TOKEN = os.getenv("API_ACCESS_TOKEN")
RATE_LIMIT = os.getenv("RATE_LIMIT_PER_MIN", "10/minute")

# --- Rate Limiting ---
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[RATE_LIMIT]
)

@app.before_request
def check_access_token():
    """Require Authorization header for all requests."""
    token = request.headers.get("Authorization")
    if not token or token.replace("Bearer ", "") != API_ACCESS_TOKEN:
        return jsonify({"error": "Unauthorized. Missing or invalid API token."}), 401


@app.route("/")
@limiter.limit("2 per minute")  # even stricter for root
def home():
    return jsonify({
        "message": "Google Maps LLM API is running securely.",
        "usage": {
            "endpoint": "/search",
            "auth": "Bearer token required",
            "rate_limit": RATE_LIMIT
        }
    })


@app.route("/search", methods=["GET"])
@limiter.limit("10 per minute")  # per client IP
def search_places():
    query = request.args.get("query")
    print("Request data: ", query)

    if not query:
        return jsonify({"error": "Missing query parameter"}), 400

    if not GOOGLE_API_KEY:
        # fallback if key missing
        return jsonify({
            "query": query,
            "warning": "Google API key not configured, returning embed link only",
            "map_embed_url": f"https://www.google.com/maps?q={query}&output=embed",
            "map_link": f"https://www.google.com/maps?q={query}"
        })

    try:
        url = (
            "https://maps.googleapis.com/maps/api/place/textsearch/json"
            f"?query={query}&key={GOOGLE_API_KEY}"
        )
        response = requests.get(url)
        data = response.json()

        print("Check log response form google: ", data)
        print("")

        if data.get("status") != "OK":
            return jsonify({
                "error": "Google API error",
                "details": data
            }), 400

        places = []
        for place in data.get("results", [])[:5]:
            name = place.get("name")
            address = place.get("formatted_address", "")
            lat = place["geometry"]["location"]["lat"]
            lng = place["geometry"]["location"]["lng"]
            map_link = f"https://www.google.com/maps?q={lat},{lng}"
            map_embed_url = f"https://www.google.com/maps?q={lat},{lng}&output=embed"
            places.append({
                "name": name,
                "address": address,
                "map_link": map_link,
                "map_embed_url": map_embed_url
            })

        return jsonify({
            "query": query,
            "count": len(places),
            "places": places
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(port=8000, debug=False)
