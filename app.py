import os
from typing import Dict, Any

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Autoriser les appels depuis ton site Firebase Hosting
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # pour un projet école. Sinon mets ton domaine précis.
    allow_methods=["*"],
    allow_headers=["*"],
)

# URLs Firebase (lecture seule)
SCAN_URL = os.getenv("SCAN_URL", "https://geolocalisation-bd77d-default-rtdb.europe-west1.firebasedatabase.app/scans.json")
LOC_URL  = os.getenv("LOC_URL",  "https://geolocalisation-bd77d-default-rtdb.europe-west1.firebasedatabase.app/localisation.json")

async def load_firebase_json(url: str) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.json()

def compute_similarity(scan_ref: Dict[str, Any], scan_live: Dict[str, Any]):
    """Score = (50 * nb BSSID communs) + Σ max(0, 100 - |ΔRSSI|)"""
    ref_map  = {ap.get("bssid"): ap for ap in (scan_ref.get("scans") or []) if ap.get("bssid")}
    live_map = {ap.get("bssid"): ap for ap in (scan_live.get("scans") or []) if ap.get("bssid")}
    commons = set(ref_map) & set(live_map)
    score = len(commons) * 50
    for b in commons:
        drssi = abs(int(ref_map[b].get("rssi", 0)) - int(live_map[b].get("rssi", 0)))
        score += max(0, 100 - drssi)
    return score, len(commons)

async def determine_location():
    scans_ref = await load_firebase_json(SCAN_URL) or {}
    scan_live = await load_firebase_json(LOC_URL)  or {}
    best = {"name": None, "score": -1, "commons": 0}
    for _, ref in scans_ref.items():
        name = ref.get("scan_name", "(sans nom)")
        s, c = compute_similarity(ref, scan_live)
        if s > best["score"]:
            best = {"name": name, "score": s, "commons": c}
    return best, scan_live

@app.get("/where")
async def where_am_i():
    best, live = await determine_location()
    return {
        "position": best["name"],
        "score": best["score"],
        "commons": best["commons"],
        "live_count": len(live.get("scans") or [])
    }

@app.get("/health")
async def health():
    return {"ok": True}

@app.get("/")
async def root():
    return {"msg": "Backend FastAPI OK. Utilise /where"}
