from fastapi import FastAPI, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import json, os
import re
import requests
from bs4 import BeautifulSoup
import functools

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "data", "menu_items.json")
HIST_PATH = os.path.join(BASE_DIR, "storage", "history.json")

MANUAL_HTML_PATH = os.path.join(BASE_DIR, "data", "manual_outlets.html")

# Heuristics so manual outlets contribute a sensible “signature dish”
PRICE_BY_CUISINE = {
    "Fast Food": 160, "North Indian": 230, "Pizza": 249, "Cafe": 199,
    "Bakery": 129, "Healthy Food": 229, "Multi-Cuisine": 209,
    "Snacks": 149, "Desserts": 149, "Beverages": 99, "Mixed": 199
}
SPICE_BY_CUISINE = {
    "Fast Food": 2.0, "North Indian": 2.5, "Pizza": 1.5, "Cafe": 1.0,
    "Bakery": 0.5, "Healthy Food": 1.0, "Multi-Cuisine": 2.0,
    "Snacks": 2.0, "Desserts": 0.2, "Beverages": 0.0, "Mixed": 2.0
}

def _primary_cuisine(raw: str) -> str:
    if not raw:
        return "Mixed"
    c = raw.split(",")[0].strip()
    return c if c in PRICE_BY_CUISINE else "Mixed"

def parse_manual_outlets_html(html: str):
    """Turn your outlet cards HTML into normalized items (1 synthetic item per outlet)."""
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(".outlet-card")
    items = []
    for c in cards:
        name_el = c.select_one(".outlet-name")
        cuisine_el = c.select_one(".outlet-cuisine")
        rating_el = c.select_one(".rating")
        if not name_el:
            continue
        name = name_el.get_text(strip=True)
        cuisine = _primary_cuisine(cuisine_el.get_text(strip=True) if cuisine_el else "Mixed")
        rating = 4.0
        if rating_el:
            m = re.search(r'(\d+(?:\.\d+)?)', rating_el.get_text(" ", strip=True))
            if m:
                try:
                    rating = float(m.group(1))
                except:
                    pass
        price = float(PRICE_BY_CUISINE.get(cuisine, 199))
        spice = float(SPICE_BY_CUISINE.get(cuisine, 2.0))
        items.append({
            "id": f"MANUAL::{name}::Signature {cuisine}",
            "name": f"Signature {cuisine}",
            "restaurant": name,
            "cuisine": cuisine,
            "veg": True,
            "spice": spice,
            "oiliness": 2.0,
            "protein": 12,
            "price": price,
            "eta_min": 25,
            "rating": rating,
            "tags": ["manual"]
        })
    return items

@functools.lru_cache(maxsize=1)
def load_manual_items():
    """Load and cache manual items from the bundled HTML file."""
    try:
        with open(MANUAL_HTML_PATH, "r", encoding="utf-8") as f:
            html = f.read()
        return parse_manual_outlets_html(html)
    except Exception:
        return []

def merge_dedupe(*lists):
    """Merge lists and dedupe by (restaurant, name) case-insensitively."""
    seen = set()
    out = []
    for L in lists:
        for it in (L or []):
            key = (str(it.get("restaurant", "")).lower(), str(it.get("name", "")).lower())
            if key in seen:
                continue
            seen.add(key)
            out.append(it)
    return out

def geocode_place(place: str):
    """Return (lat, lon) using Google if key present; else OSM. Raise on total failure."""
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if place and place.strip():
        try:
            if api_key:
                r = requests.get(
                    "https://maps.googleapis.com/maps/api/geocode/json",
                    params={"address": place, "key": api_key, "region": "in"},
                    timeout=8
                )
                j = r.json()
                res = (j.get("results") or [None])[0]
                if res and res.get("geometry"):
                    loc = res["geometry"]["location"]
                    return float(loc["lat"]), float(loc["lng"])
            # Fallback to OSM
            r = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": place, "format": "json", "limit": 1},
                headers={"User-Agent": "EatDecider/1.0"},
                timeout=8
            )
            j = r.json()
            if j:
                return float(j[0]["lat"]), float(j[0]["lon"])
        except Exception:
            pass
    # default coords as ultimate fallback (existing defaults)
    return 30.4020, 77.9680


# --- Optional sources ---
import ondc_adapter as ondc_mod
from share_importer import fetch_and_parse_share

ONDC_MODE = os.getenv("ONDC_MODE", "sandbox")
adapter = ondc_mod.ONDCAdapter(ondc_mod.ONDCSettings())

def load_menu():
    with open(DATA_PATH, "r") as f:
        return json.load(f)

def load_history():
    if not os.path.exists(HIST_PATH):
        return {"cuisine_counts": {}, "last_selected": []}
    with open(HIST_PATH, "r") as f:
        return json.load(f)

def save_history(hist):
    with open(HIST_PATH, "w") as f:
        json.dump(hist, f, indent=2)

def fees_and_total(subtotal: float):
    delivery = 30.0
    platform_fee = round(0.08 * subtotal, 2)
    tax = round(0.05 * subtotal, 2)
    coupon = 80.0 if subtotal >= 300 else (50.0 if subtotal >= 200 else 0.0)
    total = round(max(subtotal + delivery + platform_fee + tax - coupon, 0.0), 2)
    return {"subtotal": round(subtotal,2), "delivery": delivery, "platform_fee": platform_fee, "tax": tax, "discount": coupon, "total": total}

def score_item(item, user, hist):
    # Hard constraints
    if user["veg_only"] and not item["veg"]:
        return -1e9, None
    if item["eta_min"] > user["eta_limit"]:
        return -1e9, None

    # ✅ If user asked for low-oil, outright reject very oily dishes
    if user["low_oil"] and item.get("oiliness", 2.0) >= 4.0:
        return -1e9, None

    fees = fees_and_total(item["price"])
    if fees["total"] > user["budget"]:
        return -1e9, None

    # Scoring
    s = 0.0
    s += 0.6 * (item.get("rating", 4.0) - 3.5)
    s -= 0.25 * abs(user["spice"] - item.get("spice", 2.0))

    # ✅ Strong, non-linear oil penalty (kicks in beyond a gentle threshold)
    if user["low_oil"]:
        oil = float(item.get("oiliness", 2.0))
        # threshold at 2.0; quadratic dominates other small perks
        s -= 0.6 * max(0.0, oil - 2.0) ** 2
        # tiny linear term for smoother ordering inside the low range
        s -= 0.05 * max(0.0, oil - 1.5)

    # budget comfort (keep small)
    s += 0.0015 * min(fees["total"], user["budget"])

    # coupon bonus proportional to price
    s += 0.3 * (fees["discount"] / max(1.0, item["price"]))

    # ✅ ETA penalty vs YOUR limit (no hidden 30-min cap)
    s -= 0.03 * max(0.0, item["eta_min"] - user["eta_limit"])

    # novelty (less seen cuisines get a bump)
    ccount = hist["cuisine_counts"].get(item.get("cuisine", "Mixed"), 0)
    s += user["novelty"] * (1.0 / (1.0 + ccount))

    return s, fees

def build_why(item, fees, user):
    bits = []
    bits.append(f"{item['name']} from {item['restaurant']}")
    bits.append(f"{item.get('rating',4.0)}★, {item['eta_min']}m ETA")
    bits.append(f"₹{fees['total']} all-in (₹{fees['subtotal']} + del {fees['delivery']} + fee {fees['platform_fee']} + tax {fees['tax']} - disc {fees['discount']})")
    taste = []
    taste.append(f"spice {item.get('spice',2.0)}/5 vs your {user['spice']}/5")
    if user["low_oil"]:
        taste.append(f"low-oil fit: {max(0, 5-int(item.get('oiliness',2.0)) )}/5")
    if item.get("tags"):
        taste.append("tags: " + ", ".join(item["tags"][:3]))
    bits.append(" • ".join(taste))
    return " | ".join(bits)

app = FastAPI(title="Eat-Decider API", version="0.2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "Eat-Decider API", "endpoints": ["/health","/menu","/recommend","/feedback","/ondc/search","/import/share","/ingest/receipts/rebuild_history"]}

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/menu")
def menu():
    return {"items": load_menu()}

@app.get("/ondc/search")
def ondc_search(q: str, lat: float, lon: float):
    """
    Return only items that match the query tokens in name/restaurant/tags.
    This fixes sandbox catalogs that include unrelated dishes (e.g., dosa for 'biryani').
    """
    res = adapter.search_menu(q, lat, lon)
    # tokenize: alnum words, lowercased
    terms = [t for t in re.split(r'[^a-z0-9]+', q.lower()) if t]

    def matches(it: dict) -> bool:
        hay = " ".join([
            str(it.get("name", "")),
            str(it.get("restaurant", "")),
            " ".join([str(x) for x in it.get("tags", [])])
        ]).lower()
        # require ALL tokens to be present (change to any() if you want looser matching)
        return all(t in hay for t in terms) if terms else True

    filtered = [it for it in res["items"] if matches(it)]
    # fallback so the endpoint never comes back empty in weird cases
    if not filtered:
        filtered = res["items"]
    return {"source": f"ondc:{ONDC_MODE}", "items": filtered}

@app.get("/geo")
def geocode(q: str):
    """
    Resolve a place string to (lat, lon).
    - If GOOGLE_MAPS_API_KEY is set -> Google Geocoding API
    - else fallback -> Nominatim (OpenStreetMap)
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    try:
        if api_key:
            resp = requests.get(
                "https://maps.googleapis.com/maps/api/geocode/json",
                params={"address": q, "key": api_key, "region": "in"},
                timeout=8
            )
            data = resp.json()
            r = (data.get("results") or [None])[0]
            if r and r.get("geometry"):
                loc = r["geometry"]["location"]
                return {"ok": True, "lat": float(loc["lat"]), "lon": float(loc["lng"]), "source":"google"}
        # fallback to OSM
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": q, "format": "json", "limit": 1},
            headers={"User-Agent":"EatDecider/1.0"},
            timeout=8
        )
        j = resp.json()
        if j:
            return {"ok": True, "lat": float(j[0]["lat"]), "lon": float(j[0]["lon"]), "source":"osm"}
        return {"ok": False, "error": "no_results"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    
@app.get("/debug/manual")
def debug_manual():
    items = load_manual_items()
    return {"manual_count": len(items), "sample": [i["restaurant"] for i in items[:5]]}



class ShareIn(BaseModel):
    url: str
    fallback_name: Optional[str] = None
    fallback_price: Optional[float] = None
    fallback_restaurant: Optional[str] = None
    veg: Optional[bool] = None
    cuisine: Optional[str] = None

@app.post("/import/share")
def import_share(inp: ShareIn):
    data = fetch_and_parse_share(inp.url)
    if not data.get("ok"):
        item = {
            "id": f"SHARE::fallback::{inp.fallback_restaurant or 'Unknown'}::{inp.fallback_name or 'Item'}",
            "name": inp.fallback_name or "Item",
            "restaurant": inp.fallback_restaurant or "Unknown",
            "cuisine": inp.cuisine or "Mixed",
            "veg": True if inp.veg is None else bool(inp.veg),
            "spice": 2.0, "oiliness": 2.0, "protein": 10,
            "price": float(inp.fallback_price or 0.0),
            "eta_min": 30, "rating": 4.0, "tags": []
        }
    else:
        item = data["item"]
    # append to imported cache
    cache_path = os.path.join(BASE_DIR, "data", "imported_items.json")
    cache = {"items": []}
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r") as f: cache = json.load(f)
        except: pass
    cache["items"].append(item)
    with open(cache_path, "w") as f: json.dump(cache, f, indent=2)
    return {"ok": True, "item": item}

from pydantic import BaseModel

class ManualHTMLIn(BaseModel):
    html: str

@app.post("/import/manual_html")
def import_manual_html(inp: ManualHTMLIn):
    items = parse_manual_outlets_html(inp.html)
    cache_path = os.path.join(BASE_DIR, "data", "imported_items.json")
    cache = {"items": []}
    if os.path.exists(cache_path):
        try:
            cache = json.load(open(cache_path))
        except:
            pass

    merged = merge_dedupe(cache.get("items", []), items)
    with open(cache_path, "w") as f:
        json.dump({"items": merged}, f, indent=2)

    return {"ok": True, "added": len(merged) - len(cache.get("items", [])), "total_imported": len(merged)}


@app.post("/ingest/receipts/rebuild_history")
def rebuild_history_from_orders():
    orders_path = os.path.join(BASE_DIR, "storage", "orders.json")
    if not os.path.exists(orders_path):
        return {"ok": False, "error": "orders.json not found. Run tools/gmail_ingest.py first."}
    try:
        with open(orders_path, "r") as f:
            orders = json.load(f).get("orders", [])
    except Exception as e:
        return {"ok": False, "error": f"read-failed: {e}"}
    hist = load_history()
    for o in orders:
        c = o.get("cuisine") or "Mixed"
        hist["cuisine_counts"][c] = hist["cuisine_counts"].get(c, 0) + 1
    save_history(hist)
    return {"ok": True, "history": hist}

@app.get("/recommend")
def recommend(
    budget: float = Query(..., ge=50, description="Total all-in budget in INR"),
    veg_only: bool = Query(False),
    spice: float = Query(2.5, ge=0.0, le=5.0),
    low_oil: bool = Query(False),
    novelty: float = Query(0.3, ge=0.0, le=1.0),
    eta_limit: int = Query(35, ge=10, le=120),
    q: str | None = Query(None),
    lat: float | None = Query(None),
    lon: float | None = Query(None),
    place: str | None = Query(None),
    limit: int = Query(20, ge=1, le=50),   # <-- add this
):

    user = {
        "budget": budget, "veg_only": veg_only, "spice": spice,
        "low_oil": low_oil, "novelty": novelty, "eta_limit": eta_limit,
    }
    hist = load_history()

        # --- resolve coordinates (place wins; else lat/lon; else default) ---
    used_lat, used_lon = geocode_place(place) if place else (
        (lat, lon) if (lat is not None and lon is not None) else (30.4020, 77.9680)
    )

    # --- assemble sources: demo + imported + MANUAL (from HTML file) + ONDC ---
    MENU = load_menu()

    imp_path = os.path.join(BASE_DIR, "data", "imported_items.json")
    imported = []
    if os.path.exists(imp_path):
        try:
            imported = json.load(open(imp_path)).get("items", [])
        except:
            imported = []

    manual_items = load_manual_items()

    try:
        ondc_items = adapter.search_menu(q or "", used_lat, used_lon)["items"]
    except Exception:
        ondc_items = []

    MENU = merge_dedupe(MENU, imported, manual_items, ondc_items)

    # --- optional query filter (keeps biryani as biryani) ---
    if q:
        terms = [t for t in re.split(r'[^a-z0-9]+', q.lower()) if t]
        def qmatch(it: dict) -> bool:
            hay = " ".join([
                str(it.get("name","")),
                str(it.get("restaurant","")),
                " ".join([str(x) for x in it.get("tags",[])]),
            ]).lower()
            return all(t in hay for t in terms) if terms else True
        filtered = [it for it in MENU if qmatch(it)]
        if filtered:
            MENU = filtered


    # ---- scoring helper ----
    def score_all(user_cfg):
        scored = []
        for it in MENU:
            sc, fees = score_item(it, user_cfg, hist)
            if sc > -1e8:
                scored.append((sc, it, fees))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored

        # ---- score with current user settings and rank ----
    base_scored = score_all(user)
    if not base_scored:
        return {"picks": [], "note": "No items meet your constraints. Try raising budget or ETA."}

    topN = base_scored[:limit]

    def pack(rank, tup):
        sc, it, fees = tup
        return {
            "type": f"#{rank}",                 # backward compatible for the UI title
            "item": it,
            "fees": fees,
            "why": build_why(it, fees, user),
            "score": sc
        }

    picks = [pack(i, t) for i, t in enumerate(topN, start=1)]
    return {"picks": picks, "total_candidates": len(base_scored)}


class Feedback(BaseModel):
    item_id: str
    outcome: str = "selected"
    rating: float | None = None

@app.post("/feedback")
def feedback(fb: Feedback):
    hist = load_history()
    # in a real app we'd look up cuisine via a DB
    cuisine = "Mixed"
    try:
        menu = load_menu()
        for m in menu:
            if m["id"] == fb.item_id:
                cuisine = m.get("cuisine","Mixed")
                break
        # also check imported cache
        imp_path = os.path.join(BASE_DIR, "data", "imported_items.json")
        if os.path.exists(imp_path):
            for m in json.load(open(imp_path)).get("items", []):
                if m["id"] == fb.item_id:
                    cuisine = m.get("cuisine","Mixed")
                    break
    except:
        pass
    hist["cuisine_counts"][cuisine] = hist["cuisine_counts"].get(cuisine, 0) + 1
    hist["last_selected"] = (hist.get("last_selected", []) + [fb.item_id])[-10:]
    save_history(hist)
    return {"ok": True, "history": hist}
