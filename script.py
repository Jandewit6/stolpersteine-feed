import feedparser
from datetime import datetime, timedelta
import re
import hashlib
import json
import os
import html
import xml.etree.ElementTree as ET

ARCHIVE_FILE = "archive.json"
FEED_FILE = "feed.xml"
BACKUP_FILE = "feed_backup.xml"
MAX_DAYS = 365

FEED_URL_SELF = "https://jandewit6.github.io/stolpersteine-feed/feed.xml"

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


# 🔍 SCORING
def score(text):
    text = text.lower()
    s = sum(v for k, v in CONTEXT.items() if k in text)
    s -= sum(3 for w in NEGATIVE if w in text)
    return s


# 🧹 CLEAN (XML-safe)
def clean(text):
    if not text:
        return ""

    text = re.sub("<.*?>", "", text)

    for _ in range(2):
        text = html.unescape(text)

    text = re.sub(r"&[^ ]+;", " ", text)
    text = text.replace("&", "and")

    text = re.sub(r"[\x00-\x1F\x7F]", "", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text[:500]


# 🧠 SAMENVATTING
def summarize(text):
    text = clean(text)
    sentences = re.split(r'(?<=[.!?]) +', text)

    cleaned = []
    for s in sentences:
        s_lower = s.lower()

        if any(x in s_lower for x in [
            "read more", "click here", "subscribe",
            "advertisement", "cookie", "privacy"
        ]):
            continue

        if len(s.strip()) < 40:
            continue

        cleaned.append(s.strip())

    summary = " ".join(cleaned[:2])

    if not summary:
        summary = text[:200]

    return summary


# 🔐 GUID
def make_guid(link):
    return hashlib.md5(link.encode()).hexdigest()


# 📂 ARCHIEF
def load_archive():
    if not os.path.exists(ARCHIVE_FILE):
        return []
    with open(ARCHIVE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_archive(data):
    with open(ARCHIVE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# 📥 FETCH MET JUISTE DATUM
def fetch():
    items = []

    for url in FEEDS:
        feed = feedparser.parse(url)

        for e in feed.entries:
            if not e.get("link"):
                continue

            title = clean(e.get("title", ""))
            summary = summarize(e.get("summary", ""))
            link = e.get("link")

            pub = e.get("published_parsed") or e.get("updated_parsed")

            if pub:
                pub_iso = datetime(*pub[:6]).isoformat()
            else:
                pub_iso = datetime.utcnow().isoformat()

            items.append({
                "guid": make_guid(link),
                "title": title,
                "link": link,
                "description": summary,
                "pubDate": pub_iso
            })

    return items


# 🎯 FILTER
def filter_items(items, min_score):
    out = []

    for i in items:
        text = (i["title"] + " " + i["description"]).lower()

        if "stolperstein" not in text:
            continue

        if score(text) >= min_score:
            out.append(i)

    return out


# 🗂 ARCHIEF UPDATE
def update_archive(new_items, archive):
    existing = {i["link"] for i in archive}

    for item in new_items:
        if item["link"] not in existing:
            archive.append(item)

    cutoff = datetime.utcnow() - timedelta(days=MAX_DAYS)

    archive = [
        i for i in archive
        if datetime.fromisoformat(i["pubDate"]) > cutoff
    ]

    return archive


# 📡 RSS BUILD (PERFECT)
def build_rss(items):
    rss_items = ""

    for i in items[:30]:
        pubdate = datetime.fromisoformat(i["pubDate"]).strftime(
            "%a, %d %b %Y %H:%M:%S GMT"
        )

        rss_items += f"""
        <item>
          <title><![CDATA[{i['title']}]]></title>
          <link>{i['link']}</link>
          <guid isPermaLink="false">{i['guid']}</guid>
          <description><![CDATA[{i['description']}]]></description>
          <pubDate>{pubdate}</pubDate>
        </item>
        """

    build_time = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
<title>Stolpersteine News</title>
<link>https://jandewit6.github.io/stolpersteine-feed/</link>
<description>Worldwide Stolpersteine news (WWII context)</description>
<language>en</language>
<lastBuildDate>{build_time}</lastBuildDate>
<atom:link href="{FEED_URL_SELF}" rel="self" type="application/rss+xml"/>

{rss_items}

</channel>
</rss>
"""


# 🧪 VALIDATOR
def is_valid_xml(xml_string):
    try:
        ET.fromstring(xml_string)
        return True
    except Exception as e:
        print("XML ERROR:", e)
        return False


# ▶️ MAIN
def main():
    archive = load_archive()
    fetched = fetch()

    strict = filter_items(fetched, STRICT_SCORE)
    fallback = filter_items(fetched, FALLBACK_SCORE)

    if strict:
        selected = strict
    elif fallback:
        selected = fallback
    else:
        selected = fetched[:20]

    archive = update_archive(selected, archive)
    archive.sort(key=lambda x: x["pubDate"], reverse=True)

    save_archive(archive)

    new_rss = build_rss(archive)

    if is_valid_xml(new_rss):
        if os.path.exists(FEED_FILE):
            os.replace(FEED_FILE, BACKUP_FILE)

        with open(FEED_FILE, "w", encoding="utf-8") as f:
            f.write(new_rss)
    else:
        if os.path.exists(BACKUP_FILE):
            os.replace(BACKUP_FILE, FEED_FILE)


if __name__ == "__main__":
    main()
