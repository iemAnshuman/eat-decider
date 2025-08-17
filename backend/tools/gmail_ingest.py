import os, re, json, argparse, base64
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
PRICE_RX = re.compile(r'(?:₹|INR\s*)(\d+[\d,]*)')
CUISINE = [("biryani","Hyderabadi"),("dosa","South Indian"),("idli","South Indian"),("paneer","North Indian"),("dal","North Indian"),("thali","North Indian"),("noodles","Chinese"),("manchurian","Chinese"),("pizza","Italian"),("pasta","Italian"),("burger","Fast Food"),("khow suey","Burmese"),("thai","Thai"),("roll","Fast Food"),("wrap","Fast Food")]

def guess_cuisine(s: str)->str:
    s=s.lower()
    for k,v in CUISINE:
        if k in s: return v
    return "Mixed"

def parse_total(text: str):
    m = PRICE_RX.search(text)
    if not m: return None
    try: return float(m.group(1).replace(",",""))
    except: return None

def auth(creds_path:str, token_path:str):
    creds=None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path,'w') as t: t.write(creds.to_json())
    return creds

def list_msgs(svc, q):
    msgs=[]
    resp = svc.users().messages().list(userId='me', q=q, maxResults=100).execute()
    msgs+=resp.get('messages',[])
    while 'nextPageToken' in resp:
        resp = svc.users().messages().list(userId='me', q=q, pageToken=resp['nextPageToken']).execute()
        msgs+=resp.get('messages',[])
    return msgs

def fetch_full(svc, mid):
    return svc.users().messages().get(userId='me', id=mid, format='full').execute()

def decode(msg):
    parts = msg.get('payload',{}).get('parts',[])
    body = msg.get('payload',{}).get('body',{}).get('data')
    texts=[]
    if body:
        texts.append(base64.urlsafe_b64decode(body).decode('utf-8','ignore'))
    for p in parts:
        d = p.get('body',{}).get('data')
        if d:
            texts.append(base64.urlsafe_b64decode(d).decode('utf-8','ignore'))
    return "\n".join(texts)

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--creds", default=str(Path(__file__).with_name("credentials.json")))
    ap.add_argument("--token", default=str(Path(__file__).with_name("token.json")))
    ap.add_argument("--query", default="from:(zomato OR swiggy) subject:(order OR delivered) newer_than:2y")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "storage" / "orders.json"))
    args = ap.parse_args()

    svc = build('gmail','v1', credentials=auth(args.creds, args.token))
    orders=[]
    for m in list_msgs(svc, args.query):
        full = fetch_full(svc, m['id'])
        text = decode(full)
        ts = int(full.get('internalDate',0))/1000.0
        total = parse_total(text)
        if total:
            orders.append({"restaurant":"Unknown","cuisine":guess_cuisine(text),"total":total,"timestamp":ts})
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out,"w") as f: json.dump({"orders":orders}, f, indent=2)
    print(f"Wrote {len(orders)} orders to {args.out}")

if __name__ == "__main__":
    main()
