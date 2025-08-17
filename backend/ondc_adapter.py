import os, json, requests
from typing import List, Dict, Any, Optional

class ONDCSettings:
    def __init__(self):
        self.mode = os.getenv("ONDC_MODE", "sandbox")  # "live" | "sandbox"
        self.base_url = os.getenv("ONDC_BASE_URL", "").rstrip("/")
        self.timeout = int(os.getenv("ONDC_HTTP_TIMEOUT", "12"))

class ONDCAdapter:
    def __init__(self, settings: Optional[ONDCSettings] = None):
        self.s = settings or ONDCSettings()

    def search_menu(self, query: str, lat: float, lon: float) -> Dict[str, Any]:
        if self.s.mode != "live":
            sample_path = os.path.join(os.path.dirname(__file__), "ondc_samples", "search_response.json")
            raw = json.load(open(sample_path))
        else:
            if not self.s.base_url:
                raise RuntimeError("ONDC_BASE_URL not set for live mode.")
            payload = {
                "context": {
                    "domain": "nic2004:52110",
                    "action": "search",
                    "country": "IND",
                    "city": "std:080",
                    "core_version": "1.2.0",
                    "transaction_id": "tx-" + str(abs(hash((query, lat, lon)))),
                    "message_id": "msg-" + str(abs(hash(query))),
                    "ttl": "PT30S"
                },
                "message": {
                    "intent": {
                        "fulfillment": { "type": "Delivery", "end": { "location": { "gps": f"{lat},{lon}" } } },
                        "item": { "descriptor": { "name": query } }
                    }
                }
            }
            resp = requests.post(self.s.base_url + "/search", json=payload, timeout=self.s.timeout)
            resp.raise_for_status()
            raw = resp.json()
        items = self._map_items_from_search(raw)
        return {"items": items, "raw": raw}

    def _map_items_from_search(self, raw: Dict[str, Any]) -> List[Dict[str, Any]]:
        results = []
        catalogs = raw.get("message", {}).get("catalog", {})
        providers = catalogs.get("providers", []) if isinstance(catalogs, dict) else []
        for prov in providers:
            pname = (prov.get("descriptor") or {}).get("name") or prov.get("name") or "Provider"
            for it in prov.get("items", []) or []:
                name = (it.get("descriptor") or {}).get("name") or it.get("name") or "Item"
                price = 0.0
                p = it.get("price")
                if isinstance(p, dict):
                    try:
                        price = float(p.get("value") or p.get("maximum_value") or 0.0)
                    except: pass
                veg = self._guess_veg(name)
                cuisine = self._guess_cuisine(f"{name} {pname}")
                results.append({
                    "id": f"ONDC::{pname}::{name}",
                    "name": name,
                    "restaurant": pname,
                    "cuisine": cuisine,
                    "veg": veg,
                    "spice": 2.0,
                    "oiliness": 2.0,
                    "protein": 10,
                    "price": price,
                    "eta_min": 30,
                    "rating": 4.0,
                    "tags": []
                })
        return results

    def _guess_veg(self, name: str) -> bool:
        s = name.lower()
        if any(w in s for w in ["chicken","mutton","fish","egg","prawn","beef","pork"]):
            return False
        if any(w in s for w in ["paneer","dal","veg","aloo","chole","rajma","mushroom"]):
            return True
        return True

    def _guess_cuisine(self, s: str) -> str:
        s = s.lower()
        pairs = [
            ("biryani","Hyderabadi"), ("dosa","South Indian"), ("idli","South Indian"),
            ("paneer","North Indian"), ("dal","North Indian"), ("thali","North Indian"),
            ("noodles","Chinese"), ("manchurian","Chinese"), ("pizza","Italian"),
            ("pasta","Italian"), ("burger","Fast Food"), ("khow suey","Burmese"),
            ("thai","Thai"), ("roll","Fast Food"), ("wrap","Fast Food"),
        ]
        for k,v in pairs:
            if k in s: return v
        return "Mixed"
