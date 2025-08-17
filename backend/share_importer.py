import re, requests
from bs4 import BeautifulSoup

PRICE_RX = re.compile(r"(?:₹|INR\s*)(\d+[\d,]*)")

def fetch_and_parse_share(url: str):
    try:
        r = requests.get(url, timeout=12, headers={"User-Agent":"Mozilla/5.0 (compatible; EatDeciderBot/1.0)"})
        r.raise_for_status()
        html = r.text
    except Exception as e:
        return {"ok": False, "error": f"fetch-failed: {e}"}
    soup = BeautifulSoup(html, "html.parser")
    title = (soup.title.text if soup.title else "").strip()
    name = title.split("|")[0].strip() if "|" in title else title.split("-")[0].strip()
    restaurant = None
    if "|" in title:
        parts = [p.strip() for p in title.split("|")]
        if len(parts) >= 2:
            restaurant = parts[1]
    text = soup.get_text(" ", strip=True)
    m = PRICE_RX.search(text)
    price = None
    if m:
        try: price = float(m.group(1).replace(",",""))
        except: price = None
    nm = (name or "").lower()
    nonveg = any(t in nm for t in ["chicken","mutton","fish","egg","prawn","beef","pork"])
    item = {
        "id": f"SHARE::{(restaurant or 'Unknown')}::{(name or 'Item')}",
        "name": name or "Item",
        "restaurant": restaurant or "Unknown",
        "cuisine": "Mixed",
        "veg": not nonveg,
        "spice": 2.0,
        "oiliness": 2.0,
        "protein": 10,
        "price": price or 0.0,
        "eta_min": 30,
        "rating": 4.0,
        "tags": []
    }
    return {"ok": True, "item": item}
