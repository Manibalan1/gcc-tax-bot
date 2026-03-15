import feedparser
import requests
import urllib3
from bs4 import BeautifulSoup
import json
from datetime import datetime, timedelta
import time
from urllib.parse import urljoin

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIGURATION ---
# Replace with your actual Zoho Cliq Webhook URL
WEBHOOK_URL = "https://cliq.zoho.in/api/v2/channelsbyname/gcctaxnews/message?zapikey=1001.68210090936d3eddb81586cf61b1f692.48a7b6f3d5c38800b6e892f743b95f97"

SOURCES = {
    "ZATCA (KSA)": ("rss", "https://zatca.gov.sa/en/MediaCenter/News/Pages/rss.aspx"),
    "UAE FTA": ("rss", "https://tax.gov.ae/en/media.centre/news/rss.aspx"),
    "Oman Tax": ("web", "https://tms.taxoman.gov.om/portal/news"),
    "Qatar GTA": ("web", "https://gta.gov.qa/en/media-center"),
    "Bahrain BNA": ("web", "https://www.bna.bh/en/news?cms=q8FmFJgiscL2fwIzON1%2BDlBU2ciiOS%2BS%2B3GX9tqnKSw%3D"),
    "PwC Middle East": ("rss", "https://www.pwc.com/m1/en/services/tax/middle-east-tax-news-alerts/rss.xml"),
    "KPMG GCC": ("web", "https://kpmg.com/bh/en/home/insights.html"),
    "CLA Emirates": ("web", "https://www.claemirates.com/insights/"),
    "Middle East Briefing": ("web", "https://www.middleeastbriefing.com/"),
    "The National (Business)": ("web", "https://www.thenationalnews.com/business/"),
    "Bloomberg Tax": ("rss", "https://news.bloomberglaw.com/tax/rss")
}

KEYWORDS = ["tax", "vat", "zakat", "corporate", "customs", "einvoicing", "fawtara", "excise", "pillar", "dmtt", "transfer pricing"]

def send_final_report(news_items):
    today_str = datetime.now().strftime("%d %B %Y")
    
    if not news_items:
        # Professional "No News" Message
        report_text = f"📊 *GCC NEWS TODAY - {today_str}*\n\nNo tax news found today."
    else:
        # Professional News Available Message
        report_text = f"📊 *GCC NEWS TODAY - {today_str}*\n\nThe following updates were identified in the last 36 hours:\n\n"
        for item in news_items:
            report_text += f"🔹 *{item['source']}*\n{item['title']}\n🔗 {item['link']}\n\n"

    payload = {"text": report_text}
    try:
        response = requests.post(WEBHOOK_URL, json=payload, timeout=15)
        if response.status_code == 200:
            print("✅ Professional summary sent to Cliq.")
        else:
            print(f"⚠️ Cliq returned an error: {response.status_code}")
    except Exception as e:
        print(f"❌ Failed to send report: {e}")

def run_collector():
    print(f"--- 🚀 Starting Full GCC Tax Scan (36h Window) ---")
    
    # Define time window
    lookback = datetime.now() - timedelta(hours=36)
    
    # Define date patterns for web scraping
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    valid_dates = [
        today.strftime("%d %B"), yesterday.strftime("%d %B"),
        today.strftime("%b %d"), yesterday.strftime("%b %d"),
        today.strftime("%Y/%m/%d"), yesterday.strftime("%Y/%m/%d")
    ]
    
    news_buffer = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    for name, (stype, url) in SOURCES.items():
        print(f"Checking {name}...", end=" ", flush=True)
        try:
            r = requests.get(url, headers=headers, timeout=20, verify=False)
            matches_at_source = 0
            
            if stype == "rss":
                feed = feedparser.parse(r.text)
                for entry in feed.entries:
                    dt = entry.get('published_parsed')
                    if dt:
                        dt_obj = datetime.fromtimestamp(time.mktime(dt))
                        if dt_obj > lookback:
                            title = entry.get('title', 'No Title')
                            if any(k in title.lower() for k in KEYWORDS):
                                news_buffer.append({"source": name, "title": title, "link": entry.link})
                                matches_at_source += 1
            else:
                soup = BeautifulSoup(r.text, 'html.parser')
                for a in soup.find_all('a', href=True):
                    text = a.get_text(strip=True)
                    if len(text) > 30 and any(k in text.lower() for k in KEYWORDS):
                        context = (text + " " + (a.parent.get_text() if a.parent else "")).lower()
                        # Check if date matches or says "hours ago"
                        if any(d.lower() in context for d in valid_dates) or "hour ago" in context or "hours ago" in context:
                            news_buffer.append({
                                "source": name, 
                                "title": text, 
                                "link": urljoin(url, a['href'])
                            })
                            matches_at_source += 1
                            break # Get only the most recent per web page

            if matches_at_source == 0:
                print("✅")
            else:
                print(f"🔔 Found {matches_at_source}")

        except Exception:
            print("❌ Skip")

    # Send only ONE consolidated report
    send_final_report(news_buffer)

if __name__ == "__main__":
    run_collector()
