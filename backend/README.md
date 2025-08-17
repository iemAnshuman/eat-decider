# Eat-Decider Backend (FastAPI)

## Setup
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --reload
```
API runs at http://127.0.0.1:8000

## Endpoints
- `GET /health` – quick check
- `GET /menu` – returns demo menu
- `GET /recommend?budget=300&veg_only=true&spice=2.0&low_oil=false&novelty=0.3&eta_limit=30`
- `POST /feedback` – update simple history
