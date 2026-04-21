import feedparser
from datetime import datetime, timedelta
import re
import hashlib
import json
import os
import html
import traceback

ARCHIVE_FILE = "archive.json"
FEED_FILE = "feed.xml"
MAX_DAYS = 365

FEEDS = [
    "https://news.google.com/rss/search?q=stolpersteine&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=stolpersteine&hl=de&gl=DE&ceid=DE:de",
    "https://www.stolpersteine.eu/feed/",
    "https://stolpersteinecz.cz/en/feed/"
]

# 🧠 locatie herkenning
KNOWN_CITIES = {
    "zutphen": "Netherlands",
    "amsterdam": "Netherlands",
    "rotterdam": "Netherlands",
    "utrecht": "Netherlands",
    "arnhem": "Netherlands",
    "deventer": "Netherlands",
    "nijmegen": "Netherlands",
    "berlin": "Germany",
    "hamburg": "Germany",
    "vienna": "Austria",
    "prague": "Czech Republic",
    "rome": "Italy"
}


def extract_location(text):
    original = text
    text_lower = " " + text.lower() + " "

    for city, country in KNOWN_CITIES.items():
        if f" {city} " in text_lower:
            return city.title(), country

    match = re.search(r"\bin ([A-Z][a-zA-Z\-]+)", original)
    if match:
        return match.group(1), "Unknown"

    match = re.search(r"\b(?:in|near|from) ([A-Z][a-zA-Z\-]+)", original)
    if match:
        return match.group(1), "Unknown"

    words = original.split()
    for w in words:
        if len(w) > 4 and w[0].isupper():
            if w.lower() not in ["stolpersteine", "holocaust", "nazi"]:
                return w, "Unknown"

    return "Unknown", "Unknown"


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


def summarize(text):
    text = clean(text)
    sentences = re.split(r'(?<=[.!?]) +', text)
    return " ".join(sentences[:2])[:300]


def make_id(link):
    return hashlib.md5(link.encode()).hexdigest()


def load_archive():
    if not os.path.exists(ARCHIVE_FILE):
        return []
    with open(ARCHIVE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_archive(data):
    with open(ARCHIVE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fetch():
    items = []

    for url in FEEDS:
        feed = feedparser.parse(url)

        for e in feed.entries:
            try:
                link = e.get("link")
                if not link:
                    continue

                title = clean(e.get("title", ""))
                summary = summarize(e.get("summary", ""))

                city, country = extract_location(title + " " + summary)

                pub = e.get("published_parsed") or e.get("updated_parsed")

                if pub:
                    pub_iso = datetime(*pub[:6]).isoformat()
                else:
                    pub_iso = datetime.utcnow().isoformat()

                items.append({
                    "id": make_id(link),
                    "title": title,
                    "link": link,
                    "description": summary,
                    "pubDate": pub_iso,
                    "city": city,
                    "country": country
                })

            except Exception as e:
                print("item error:", e)

    return items


def update_archive(new_items, archive):
    existing = {i.get("link") for i in archive}

    for item in new_items:
        if item["link"] not in existing:
            archive.append(item)

    cutoff = datetime.utcnow() - timedelta(days=MAX_DAYS)

    return [
        i for i in archive
        if datetime.fromisoformat(i["pubDate"]) > cutoff
    ]


def build_rss(items):
    rss_items = ""

    for i in items[:30]:
        try:
            pubdate = datetime.fromisoformat(i["pubDate"]).strftime(
                "%a, %d %b %Y %H:%M:%S GMT"
            )
        except:
            pubdate = datetime.utcnow().strftime(
                "%a, %d %b %Y %H:%M:%S GMT"
            )

        guid = i.get("id") or make_id(i["link"])

        location = f"{i['city']}, {i['country']}" if i["city"] != "Unknown" else "Unknown"

        description = f"{i['description']} (Location: {location})"

        rss_items += f"""
        <item>
          <title><![CDATA[{i['title']}]]></title>
          <link>{i['link']}</link>
          <guid>{guid}</guid>
          <description><![CDATA[{description}]]></description>
          <pubDate>{pubdate}</pubDate>
        </item>
        """

    build_time = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>Stolpersteine News</title>
<link>https://jandewit6.github.io/stolpersteine-feed/</link>
<description>Stolpersteine news with locations</description>
<lastBuildDate>{build_time}</lastBuildDate>
{rss_items}
</channel>
</rss>
"""


def main():
    archive = load_archive()
    fetched = fetch()

    archive = update_archive(fetched, archive)
    archive.sort(key=lambda x: x["pubDate"], reverse=True)

    save_archive(archive)

    rss = build_rss(archive)

    with open(FEED_FILE, "w", encoding="utf-8") as f:
        f.write(rss)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("ERROR:", e)
        traceback.print_exc()
        raise
