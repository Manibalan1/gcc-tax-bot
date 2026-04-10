import feedparser
import requests
import urllib3
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import time
from urllib.parse import urljoin
import json
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

WEBHOOK_URL = "https://cliq.zoho.in/api/v2/channelsbyname/gcctaxnews/message?zapikey=1001.68210090936d3eddb81586cf61b1f692.48a7b6f3d5c38800b6e892f743b95f97"

HEADERS = {'User-Agent': 'Mozilla/5.0'}

LOOKBACK = datetime.now() - timedelta(hours=36)

# --- KEYWORDS ---
STRONG_KEYWORDS = [
    "vat", "tax", "zakat", "corporate tax",
    "excise", "customs", "e-invoicing",
    "transfer pricing", "tax law"
]

EXCLUDE_WORDS = [
    "sports", "movie", "celebrity",
    "fashion", "lifestyle"
]

def is_relevant(text):
    t = text.lower()
    return any(k in t for k in STRONG_KEYWORDS)

def is_noise(text):
    t = text.lower()
    return any(x in t for x in EXCLUDE_WORDS)

# --- FETCH HTML ---
def fetch(url):
    try:
        return requests.get(url, headers=HEADERS, timeout=10).text
    except:
        return ""

# --- DATE PARSER ---
def parse_date(date_str):
    try:
        return datetime.fromisoformat(date_str.replace("Z", ""))
    except:
        return None

# --- EXTRACT DATE (META + JSON + REGEX) ---
def extract_date(soup, html):
    # 1. META TAGS
    meta_keys = [
        ("property", "article:published_time"),
        ("name", "publish-date"),
        ("name", "pubdate"),
        ("itemprop", "datePublished")
    ]

    for key, val in meta_keys:
        tag = soup.find("meta", {key: val})
        if tag and tag.get("content"):
            dt = parse_date(tag["content"])
            if dt:
                return dt

    # 2. JSON-LD (very important)
    scripts = soup.find_all("script", type="application/ld+json")
    for s in scripts:
        try:
            data = json.loads(s.string)
            if isinstance(data, dict):
                if "datePublished" in data:
                    dt = parse_date(data["datePublished"])
                    if dt:
                        return dt
        except:
            continue

    # 3. REGEX fallback
    match = re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", html)
    if match:
        return parse_date(match.group())

    return None

# --- PROCESS ARTICLE ---
def process_article(source, title, link):
    html = fetch(link)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")
    article_date = extract_date(soup, html)

    if not article_date:
        return None

    if article_date > LOOKBACK:
        return {
            "source": source,
            "title": title,
            "link": link
        }

    return None

# --- RSS HANDLER ---
def handle_rss(name, url):
    results = []
    try:
        feed = feedparser.parse(requests.get(url, timeout=10).text)

        for entry in feed.entries[:15]:
            dt = entry.get('published_parsed') or entry.get('updated_parsed')
            if not dt:
                continue

            dt_obj = datetime.fromtimestamp(time.mktime(dt))

            if dt_obj > LOOKBACK:
                title = entry.get('title', '')

                if is_relevant(title) and not is_noise(title):
                    results.append({
                        "source": name,
                        "title": title,
                        "link": entry.link
                    })
    except:
        pass

    return results

# --- WEB HANDLER ---
def handle_web(name, url):
    results = []
    html = fetch(url)

    if not html:
        return results

    soup = BeautifulSoup(html, "html.parser")

    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True)

        if len(text) > 40:
            if is_relevant(text) and not is_noise(text):

                link = urljoin(url, a["href"])
                article = process_article(name, text, link)

                if article:
                    results.append(article)
                    print("✅", text[:60])

                    if len(results) >= 2:
                        break

    return results

# --- SOURCES ---
SOURCES = {
    "ZATCA": ("rss", "https://zatca.gov.sa/en/MediaCenter/News/Pages/rss.aspx"),
    "UAE FTA": ("rss", "https://tax.gov.ae/en/media.centre/news/rss.aspx"),
    "PwC": ("rss", "https://www.pwc.com/m1/en/services/tax/middle-east-tax-news-alerts/rss.xml"),

    "Khaleej Times": ("web", "https://www.khaleejtimes.com/business"),
    "Gulf News": ("web", "https://gulfnews.com/"),
    "Arab News": ("web", "https://www.arabnews.com/business-economy"),
    "Zawya": ("web", "https://www.zawya.com/en/economy/gcc")
}

# --- SEND ---
def send(news):
    today = datetime.now().strftime("%d %B %Y")

    if not news:
        msg = f"📊 GCC TAX NEWS - {today}\n\nNo updates in last 36 hours."
    else:
        msg = f"📊 GCC TAX NEWS - {today}\n\n"
        for n in news:
            msg += f"🔹 {n['source']}\n{n['title']}\n{n['link']}\n\n"

    requests.post(WEBHOOK_URL, json={"text": msg})

# --- MAIN ---
def run():
    print("🚀 ULTIMATE TAX ENGINE (FAST + STRICT)")

    news = []

    for name, (stype, url) in SOURCES.items():
        print(f"\nChecking {name}...")

        if stype == "rss":
            news += handle_rss(name, url)
        else:
            news += handle_web(name, url)

        time.sleep(1)

    # REMOVE DUPLICATES
    seen = set()
    clean = []

    for n in news:
        if n["title"] not in seen:
            seen.add(n["title"])
            clean.append(n)

    send(clean)

# --- RUN ---
if __name__ == "__main__":
    run()
