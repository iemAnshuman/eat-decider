# Eat-Decider (Beginner-friendly End-to-End)

This is a copy-pasteable MVP that chooses food for you based on budget, veg preference, spice, ETA, and novelty. It returns **Safe**, **Value**, and **Adventure** picks with **all-in pricing** (fees, tax, coupon) and a one-line explanation.

## Prereqs
- Python 3.10+
- Node 18+ and npm

## Run
### 1) Backend
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --reload
```
Backend: http://127.0.0.1:8000

### 2) Frontend
Open a new terminal:
```bash
cd frontend
npm i
npm run dev
```
Frontend: http://localhost:5173

## How to use
1. Set **Budget (₹ all-in)**, **ETA limit**, **Veg only**, **Spice**, **Novelty**, and **Low-oil**.
2. Click **Get Picks**. You’ll see three cards.
3. Click **Decide this** on the one you want. This updates a tiny history so the app increases variety over time.
4. Order that item in your food app. (We don’t auto-order.)

## Files to look at
- `backend/app.py` — the scoring function and API endpoints.
- `backend/data/menu_items.json` — demo menu you can edit to match your city.
- `backend/storage/history.json` — simple on-disk memory for cuisine variety.
- `frontend/src/App.jsx` — the UI and API calls.

## Next steps (optional)
- Replace demo data with a real menu export.
- Add calories/macros to items and a “Health mode” target.
- Per-user accounts (Postgres) + auth.
- Real contextual features (weather, surge fees).
- Better exploration using a contextual bandit (Thompson sampling).
