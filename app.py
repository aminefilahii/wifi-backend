from flask import Flask, jsonify
from flask_cors import CORS
import requests, os

app = Flask(__name__)
CORS(app)  # autorise les appels cross-origin depuis ton site Firebase

# URLs Firebase (lecture seule)
SCAN_URL = os.getenv("SCAN_URL", "https://geolocalisation-bd77d-default-rtdb.europe-west1.firebasedatabase.app/scans.json")
LOC_URL  = os.getenv("LOC_URL",  "https://geolocalisation-bd77d-default-rtdb.europe-west1.firebasedatabase.app/localisation.json")

def load_firebase_json(url):
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()

def compute_similarity(scan_ref, scan_live):
    score = 0
    ref_map  = {ap.get("bssid"): ap for ap in scan_ref.get("scans", []) if ap.get("bssid")}
    live_map = {ap.get("bssid"): ap for ap in scan_live.get("scans", []) if ap.get("bssid")}
    commons = set(ref_map.keys()) & set(live_map.keys())

    score += len(commons) * 50  # bonus nombre de BSSID communs
    for b in commons:
        drssi = abs(int(ref_map[b].get("rssi", 0)) - int(live_map[b].get("rssi", 0)))
        score += max(0, 100 - drssi)  # RSSI proche => meilleur score
    return score, len(commons)

def determine_location():
    scans_ref = load_firebase_json(SCAN_URL) or {}
    scan_live = load_firebase_json(LOC_URL)  or {}
    best = {"name": None, "score": -1, "commons": 0}

    for _, ref in scans_ref.items():
        name = ref.get("scan_name", "(sans nom)")
        s, c = compute_similarity(ref, scan_live)
        if s > best["score"]:
            best = {"name": name, "score": s, "commons": c}
    return best, scan_live

@app.get("/where")
def where_am_i():
    best, live = determine_location()
    return jsonify({
        "position": best["name"],
        "score": best["score"],
        "commons": best["commons"],
        "live_count": len(live.get("scans", []))
    })

@app.get("/health")
def health():
    return "ok", 200

@app.get("/")
def root():
    return "Backend Flask OK. Utilise /where", 200

if __name__ == "__main__":
    # Render lancera avec gunicorn, mais utile en local
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
