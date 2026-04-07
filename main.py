import feedparser
import requests
import urllib3
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import time
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright
import os

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- WEBHOOK FROM GITHUB SECRET ---
WEBHOOK_URL = "https://cliq.zoho.in/api/v2/channelsbyname/gcctaxnews/message?zapikey=1001.68210090936d3eddb81586cf61b1f692.48a7b6f3d5c38800b6e892f743b95f97"

# --- JS SITES ---
JS_SITES = [
    "Khaleej Times",
    "Gulf News UAE",
    "The National",
    "The National (Business)"
]

# --- SOURCES ---
SOURCES = {
    "ZATCA (KSA)": ("rss", "https://zatca.gov.sa/en/MediaCenter/News/Pages/rss.aspx"),
    "UAE FTA": ("rss", "https://tax.gov.ae/en/media.centre/news/rss.aspx"),
    "PwC Middle East": ("rss", "https://www.pwc.com/m1/en/services/tax/middle-east-tax-news-alerts/rss.xml"),
    "Bloomberg Tax": ("rss", "https://news.bloomberglaw.com/tax/rss"),

    "Oman Tax": ("web", "https://tms.taxoman.gov.om/portal/news"),
    "Qatar GTA": ("web", "https://gta.gov.qa/en/media-center"),
    "Bahrain BNA": ("web", "https://bna.bh"),
    "KPMG GCC": ("web", "https://kpmg.com/bh/en/home/insights.html"),
    "CLA Emirates": ("web", "https://www.claemirates.com/insights/"),
    "Middle East Briefing": ("web", "https://www.middleeastbriefing.com/"),

    "The National (Business)": ("web", "https://www.thenationalnews.com/business/"),
    "The National": ("web", "https://www.thenationalnews.com/business/"),
    "Khaleej Times": ("web", "https://www.khaleejtimes.com/business"),
    "Gulf News UAE": ("web", "https://gulfnews.com/"),
    "Arab News": ("web", "https://www.arabnews.com/business-economy"),
    "Al Arabiya": ("web", "https://english.alarabiya.net/business"),
    "The Peninsula Qatar": ("web", "https://thepeninsulaqatar.com/business/"),
    "Gulf Times": ("web", "https://www.gulf-times.com/"),
    "Al Jazeera Business": ("web", "https://www.aljazeera.com/economy/"),
    "Times of Oman": ("web", "https://timesofoman.com/"),
    "Muscat Daily": ("web", "https://muscatdaily.com/"),
    "Kuwait Times": ("web", "https://www.kuwaittimes.com/"),
    "Arab Times Kuwait": ("web", "https://www.arabtimesonline.com/"),
    "Gulf Daily News": ("web", "https://www.gdnonline.com/"),

    "Bahrain National Bureau for Revenue": ("web", "https://nbr.gov.bh", "page"),
    "Dubai Customs": ("web", "https://dubaicustoms.gov.ae", "page"),

    "Central Bank of UAE": ("web", "https://centralbank.ae", None),
    "Qatar Central Bank": ("web", "https://qcb.gov.qa", None),

    "Saudi Press Agency (SPA)": ("web", "https://spa.gov.sa", "page"),
    "Emirates News Agency (WAM)": ("web", "https://wam.ae", None),
    "Bahrain News Agency (BNA Official)": ("web", "https://bna.bh", "page"),
    
    "Zawya GCC Economy": ("web", "https://www.zawya.com/en/economy/gcc", None),
    "Arab News Business": ("web", "https://arabnews.com", None),
    "KPMG Gulf Insights": ("web", "https://kpmg.com", None),
    "Gulf Business": ("web", "https://gulfbusiness.com", None),
    "Argaam News": ("web", "https://argaam.com", None)
}

# --- FILTERING ---
STRONG_KEYWORDS = [
    "vat", "value added tax", "zakat",
    "corporate tax", "withholding tax",
    "excise tax", "customs duty",
    "transfer pricing",
    "e-invoicing", "einvoicing", "e-invoice",
    "reverse charge",
    "tax authority", "tax law", "tax reform",
    "pillar two"
]

EXCLUDE_WORDS = [
    "climate", "sports", "war", "fashion",
    "lifestyle", "movie", "celebrity",
    "music", "art", "lifestyle", "art-fashion"
]

def is_relevant(title):
    t = title.lower()
    return any(k in t for k in STRONG_KEYWORDS)

def is_noise(title):
    t = title.lower()
    return any(x in t for x in EXCLUDE_WORDS)

# --- PLAYWRIGHT FIXED ---
def fetch_rendered_html(url):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox"]
            )
            page = browser.new_page()
            page.goto(url, timeout=60000)
            page.wait_for_timeout(4000)
            html = page.content()
            browser.close()
            return html
    except Exception as e:
        print(f"❌ Playwright error: {e}")
        return ""

# --- SAFE FETCH ---
def fetch_html(name, url, headers):
    try:
        if name in JS_SITES:
            print("⚡ JS", end=" ")
            return fetch_rendered_html(url)
        else:
            print("🌐 HTTP", end=" ")
            r = requests.get(url, headers=headers, timeout=20, verify=False)
            return r.text
    except Exception as e:
        print(f"❌ Fetch error: {e}")
        return ""

# --- SEND REPORT ---
def send_final_report(news_items):
    today_str = datetime.now().strftime("%d %B %Y")

    if not news_items:
        report_text = f"📊 *GCC TAX NEWS - {today_str}*\n\nNo relevant tax updates in the last 36 hours."
    else:
        report_text = f"📊 *GCC TAX NEWS - {today_str}*\n\nLatest regulatory and tax updates:\n\n"

        for item in news_items:
            report_text += f"🔹 *{item['source']}*\n{item['title']}\n🔗 {item['link']}\n\n"

    payload = {"text": report_text}

    try:
        response = requests.post(WEBHOOK_URL, json=payload, timeout=15)
        if response.status_code == 200:
            print("✅ Sent to Zoho Cliq")
        else:
            print(f"⚠️ Error sending: {response.status_code}")
    except Exception as e:
        print(f"❌ Webhook failed: {e}")

# --- MAIN ---
def run_collector():
    print("--- 🚀 GCC TAX INTELLIGENCE ENGINE ---")

    lookback = datetime.now() - timedelta(hours=36)
    news_buffer = []
    headers = {'User-Agent': 'Mozilla/5.0'}

    for name, source_data in SOURCES.items():
        stype = source_data[0]
        url = source_data[1]

        print(f"\nChecking {name}...", end=" ")

        try:
            matches = 0

            # --- RSS ---
            if stype == "rss":
                print("📡 RSS", end=" ")
                r = requests.get(url, headers=headers, timeout=20)
                feed = feedparser.parse(r.text)

                for entry in feed.entries:
                    dt = entry.get('published_parsed')

                    if dt:
                        dt_obj = datetime.fromtimestamp(time.mktime(dt))

                        if dt_obj > lookback:
                            title = entry.get('title', '')

                            if is_relevant(title) and not is_noise(title):
                                news_buffer.append({
                                    "source": name,
                                    "title": title,
                                    "link": entry.link
                                })
                                matches += 1

            # --- WEB ---
            else:
                html = fetch_html(name, url, headers)

                if not html:
                    print("❌ No content")
                    continue

                soup = BeautifulSoup(html, 'html.parser')

                for a in soup.find_all('a', href=True):
                    text = a.get_text(strip=True)

                    if len(text) > 40:
                        if is_relevant(text) and not is_noise(text):
                            news_buffer.append({
                                "source": name,
                                "title": text,
                                "link": urljoin(url, a['href'])
                            })
                            matches += 1
                            print("Source:", name, "| Title:", text, "| Link:", urljoin(url, a['href']))

                            if matches >= 2:
                                break

            print(f"🔔 {matches} found")
            time.sleep(2)

        except Exception as e:
            print(f"❌ Error: {e}")

    # --- REMOVE DUPLICATES ---
    seen = set()
    clean_news = []

    for item in news_buffer:
        if item['title'] not in seen:
            seen.add(item['title'])
            clean_news.append(item)

    send_final_report(clean_news)

# --- RUN ---
if __name__ == "__main__":
    run_collector()
