# Eat-Decider Backend (FastAPI)

## Setup
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --reload
```
API: http://127.0.0.1:8000

### Endpoints
- `GET /` → list of endpoints
- `GET /health`
- `GET /menu`
- `GET /recommend?budget=300&veg_only=true&spice=2.0&low_oil=false&novelty=0.3&eta_limit=30`
- `POST /feedback`

### ONDC (sandbox or live)
```
export ONDC_MODE=sandbox   # default; uses backend/ondc_samples/search_response.json
# For live:
# export ONDC_MODE=live
# export ONDC_BASE_URL=https://<your-ondc-gateway>
```
- `GET /ondc/search?q=biryani&lat=30.4020&lon=77.9680`

### Share-link importer (public pages only)
`POST /import/share` with JSON:
```json
{
  "url": "https://example.com/public/share",
  "fallback_name": "Paneer Butter Masala",
  "fallback_price": 199,
  "fallback_restaurant": "Tasty Treat",
  "veg": true,
  "cuisine": "North Indian"
}
```
Adds to `data/imported_items.json`.

### Gmail receipts → orders.json
```
cd tools
# put Google OAuth credentials.json here (Desktop app)
python gmail_ingest.py --query "from:(zomato OR swiggy) subject:(order OR delivered) newer_than:2y"
```
Then seed history:
```
curl -X POST http://127.0.0.1:8000/ingest/receipts/rebuild_history
```

