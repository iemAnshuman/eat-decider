# Eat-Decider (ONDC + Receipts + Share Links)

## Run
1) Backend
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export ONDC_MODE=sandbox
uvicorn app:app --reload
```

2) Frontend
```bash
cd ../frontend
npm i
npm run dev
```

- Use the **Use ONDC source** toggle to warm ONDC (sandbox) search.
- `/import/share` adds public page items to `data/imported_items.json`.
- `tools/gmail_ingest.py` pulls receipts into `storage/orders.json`, then POST `/ingest/receipts/rebuild_history` to seed cuisine counts.

