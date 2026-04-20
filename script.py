import feedparser
from datetime import datetime, timedelta
import re
import hashlib
import json
import os
import html

ARCHIVE_FILE = "archive.json"
MAX_DAYS = 365

FEEDS = [
    "https://news.google.com/rss/search?q=stolpersteine&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=stolpersteine&hl=de&gl=DE&ceid=DE:de",
    "https://news.google.com/rss/search?q=stolpersteine&hl=it&gl=IT&ceid=IT:it",
    "https://www.stolpersteine.eu/feed/",
    "https://stolpersteinecz.cz/en/feed/"
]

CONTEXT = {
    "holocaust": 3, "shoah": 3,
    "nazi": 3, "world war ii": 3,
    "wwii": 3, "auschwitz": 3,
    "deport": 2, "jew": 2,
    "victim": 2, "memorial": 2,
    "commemoration": 2, "persecution": 2
}

NEGATIVE = ["football", "club", "restaurant", "music"]

STRICT_SCORE = 5
FALLBACK_SCORE = 2


# 🔍 score berekening
def score(text):
    text = text.lower()
    s = sum(v for k, v in CONTEXT.items() if k in text)
    s -= sum(3 for w in NEGATIVE if w in text)
    return s


# 🧹 XML-veilige tekst
def clean(text):
    # verwijder HTML tags
    text = re.sub("<.*?>", "", text)

    # decode HTML entities (&nbsp; etc.)
    text = html.unescape(text)

    # verwijder rare control chars
    text = re.sub(r"[\x00-\x1F\x7F]", "", text)

    # maak XML-safe
    text = text.replace("&", "&amp;")
    text = text.replace("<", "").replace(">", "")

    text = text.replace("\n", " ").strip()

    return text[:500]


# 🔐 unieke id
def make_id(title, link):
    return hashlib.md5((title + link).lower().encode()).hexdigest()


# 📂 archief laden
def load_archive():
    if not os.path.exists(ARCHIVE_FILE):
        return []
    with open(ARCHIVE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# 💾 archief opslaan
def save_archive(data):
    with open(ARCHIVE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# 📥 ophalen
def fetch():
    items = []

    for url in FEEDS:
        feed = feedparser.parse(url)

        for e in feed.entries:
            if not e.get("published_parsed"):
                continue

            title = e.get("title", "")
            link = e.get("link", "")
            summary = e.get("summary", "")

            items.append({
                "id": make_id(title, link),
                "title": clean(title),
                "link": link,
                "description": clean(summary),
                "pubDate": datetime(*e.published_parsed[:6]).isoformat()
            })

    return items


# 🎯 filtering
def filter_items(items, min_score):
    out = []

    for i in items:
        text = (i["title"] + " " + i["description"]).lower()

        if "stolperstein" not in text:
            continue

        if score(text) >= min_score:
            out.append(i)

    return out


# 🗂 archief updaten
def update_archive(new_items, archive):
    existing_links = {i["link"] for i in archive}

    for item in new_items:
        if item["link"] not in existing_links:
            archive.append(item)

    cutoff = datetime.utcnow() - timedelta(days=MAX_DAYS)

    archive = [
        i for i in archive
        if datetime.fromisoformat(i["pubDate"]) > cutoff
    ]

    return archive


# 📡 RSS bouwen
def build_rss(items):
    rss_items = ""

    for i in items[:30]:
        pubdate = datetime.fromisoformat(i["pubDate"]).strftime(
            "%a, %d %b %Y %H:%M:%S GMT"
        )

        rss_items += f"""
        <item>
          <title>{i['title']}</title>
          <link>{i['link']}</link>
          <description>{i['description']}</description>
          <pubDate>{pubdate}</pubDate>
        </item>
        """

    return f"""<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
<channel>
<title>Stolpersteine News</title>
<link>https://YOUR_USERNAME.github.io/stolpersteine-feed/</link>
<description>Fallback-proof Stolpersteine RSS (WWII context)</description>
{rss_items}
</channel>
</rss>
"""


# ▶️ main
def main():
    archive = load_archive()
    fetched = fetch()

    print(f"Fetched: {len(fetched)} items")

    # 🧠 strikt
    strict = filter_items(fetched, STRICT_SCORE)
    print(f"Strict: {len(strict)}")

    if strict:
        selected = strict
    else:
        # ⚠️ fallback
        fallback = filter_items(fetched, FALLBACK_SCORE)
        print(f"Fallback: {len(fallback)}")

        if fallback:
            selected = fallback
        else:
            # 🧯 laatste redmiddel
            print("Using last resort (no filter)")
            selected = fetched[:20]

    archive = update_archive(selected, archive)

    archive.sort(key=lambda x: x["pubDate"], reverse=True)

    save_archive(archive)

    rss = build_rss(archive)

    with open("feed.xml", "w", encoding="utf-8") as f:
        f.write(rss)


if __name__ == "__main__":
    main()
