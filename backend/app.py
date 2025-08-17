from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json, os, math, time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "data", "menu_items.json")
HIST_PATH = os.path.join(BASE_DIR, "storage", "history.json")

with open(DATA_PATH, "r") as f:
    MENU = json.load(f)

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
    coupon = 0.0
    # simple demo coupon rules
    if subtotal >= 300:
        coupon = 80.0
    elif subtotal >= 200:
        coupon = 50.0
    total = round(max(subtotal + delivery + platform_fee + tax - coupon, 0.0), 2)
    return {
        "subtotal": round(subtotal, 2),
        "delivery": delivery,
        "platform_fee": platform_fee,
        "tax": tax,
        "discount": coupon,
        "total": total
    }

def score_item(item, user, hist):
    # Hard constraints
    if user["veg_only"] and not item["veg"]:
        return -1e9, None
    if item["eta_min"] > user["eta_limit"]:
        return -1e9, None
    fees = fees_and_total(item["price"])
    if fees["total"] > user["budget"]:
        return -1e9, None

    # Scoring terms (simple, interpretable)
    s = 0.0
    # Ratings (center at 3.5)
    s += 0.6 * (item["rating"] - 3.5)
    # Spice alignment (0..5)
    s -= 0.25 * abs(user["spice"] - item["spice"])
    # Oiliness penalty if user asked for low oil
    if user["low_oil"]:
        s -= 0.15 * item["oiliness"]
    # Prefer spending budget but staying under
    # Slight reward for higher spend under cap
    s += 0.002 * min(fees["total"], user["budget"])
    # Reward discounts
    s += 0.3 * (fees["discount"] / max(1.0, item["price"]))
    # ETA penalty when close to user's limit
    s -= 0.03 * max(0.0, item["eta_min"] - min(user["eta_limit"], 30))

    # Novelty based on cuisine frequency
    ccount = hist["cuisine_counts"].get(item["cuisine"], 0)
    novelty_bonus = user["novelty"] * (1.0 / (1.0 + ccount))
    s += novelty_bonus

    return s, fees

def build_why(item, fees, user):
    bits = []
    bits.append(f"{item['name']} from {item['restaurant']}")
    bits.append(f"{item['rating']}★, {item['eta_min']}m ETA")
    bits.append(f"₹{fees['total']} all-in (₹{fees['subtotal']} + del {fees['delivery']} + fee {fees['platform_fee']} + tax {fees['tax']} - disc {fees['discount']})")
    # Taste notes
    taste = []
    taste.append(f"spice {item['spice']}/5 vs your {user['spice']}/5")
    if user["low_oil"]:
        taste.append(f"low-oil fit: {max(0, 5-int(item['oiliness']))}/5")
    if item["tags"]:
        taste.append("tags: " + ", ".join(item["tags"][:3]))
    bits.append(" • ".join(taste))
    return " | ".join(bits)

app = FastAPI(title="Eat-Decider API", version="0.1")

# CORS for local dev (Vite default 5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/menu")
def menu():
    return {"items": MENU}

@app.get("/recommend")
def recommend(
    budget: float = Query(..., ge=50, description="Total all-in budget in INR"),
    veg_only: bool = Query(False),
    spice: float = Query(2.5, ge=0.0, le=5.0),
    low_oil: bool = Query(False),
    novelty: float = Query(0.3, ge=0.0, le=1.0),
    eta_limit: int = Query(35, ge=10, le=120)
):
    user = {
        "budget": budget,
        "veg_only": veg_only,
        "spice": spice,
        "low_oil": low_oil,
        "novelty": novelty,
        "eta_limit": eta_limit,
    }
    hist = load_history()

    scored = []
    for it in MENU:
        sc, fees = score_item(it, user, hist)
        if sc > -1e8:
            scored.append((sc, it, fees))

    if not scored:
        return {"picks": [], "note": "No items meet your constraints. Try raising budget or ETA."}

    # Sort by score desc
    scored.sort(key=lambda x: x[0], reverse=True)

    # Safe = top score
    safe_sc, safe_it, safe_fees = scored[0]

    # Value = best rating / total price
    best_val = max(scored, key=lambda x: (x[1]["rating"] / max(1.0, x[2]["total"])))

    # Adventure = highest score with different cuisine than safe, prioritizing rarity
    safe_cuisine = safe_it["cuisine"]
    # Rank by (score + novelty weight based on low cuisine count)
    def adv_key(x):
        it = x[1]
        ccount = hist["cuisine_counts"].get(it["cuisine"], 0)
        return x[0] + user["novelty"] * (1.0 / (1.0 + ccount))

    adventure_candidates = [x for x in scored if x[1]["cuisine"] != safe_cuisine]
    adv_tuple = max(adventure_candidates, key=adv_key) if adventure_candidates else scored[1 if len(scored)>1 else 0]

    picks = []
    picks.append({
        "type": "Safe",
        "item": safe_it,
        "fees": safe_fees,
        "why": build_why(safe_it, safe_fees, user)
    })
    picks.append({
        "type": "Value",
        "item": best_val[1],
        "fees": best_val[2],
        "why": build_why(best_val[1], best_val[2], user)
    })
    picks.append({
        "type": "Adventure",
        "item": adv_tuple[1],
        "fees": adv_tuple[2],
        "why": build_why(adv_tuple[1], adv_tuple[2], user)
    })

    return {"picks": picks}

class Feedback(BaseModel):
    item_id: str
    outcome: str = "selected"  # selected / ordered / disliked
    rating: float | None = None

@app.post("/feedback")
def feedback(fb: Feedback):
    hist = load_history()
    # Update cuisine counts
    matches = [m for m in MENU if m["id"] == fb.item_id]
    if matches:
        cuisine = matches[0]["cuisine"]
        hist["cuisine_counts"][cuisine] = hist["cuisine_counts"].get(cuisine, 0) + 1
    # Track last selected
    hist["last_selected"] = (hist.get("last_selected", []) + [fb.item_id])[-10:]
    save_history(hist)
    return {"ok": True, "history": hist}
