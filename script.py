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
    "https://news.google.com/rss/search?q=stolpersteine&hl=it&gl=IT&ceid=IT:it",
    "https://www.stolpersteine.eu/feed/",
    "https://stolpersteinecz.cz/en/feed/"
]

STRICT_SCORE = 5
FALLBACK_SCORE = 2


# 🔍 score
def score(text):
    text = text.lower()
    keywords = ["holocaust", "nazi", "wwii", "auschwitz", "deport", "jew", "victim"]
    return sum(2 for k in keywords if k in text)


# 🧹 clean (XML safe)
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


# 🧠 samenvatting
def summarize(text):
    text = clean(text)
    sentences = re.split(r'(?<=[.!?]) +', text)
    return " ".join(sentences[:2])[:300]


# 🔐 id
def make_id(link):
    return hashlib.md5(link.encode()).hexdigest()


# 📂 archief
def load_archive():
    if not os.path.exists(ARCHIVE_FILE):
        return []
    with open(ARCHIVE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_archive(data):
    with open(ARCHIVE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# 📥 fetch
def fetch():
    items = []

    for url in FEEDS:
        print("Fetching:", url)
        feed = feedparser.parse(url)

        for e in feed.entries:
            try:
                link = e.get("link")
                if not link:
                    continue

                title = clean(e.get("title", ""))
                summary = summarize(e.get("summary", ""))

                # pubdate
                pub = None
                if hasattr(e, "published_parsed") and e.published_parsed:
                    pub = e.published_parsed
                elif hasattr(e, "updated_parsed") and e.updated_parsed:
                    pub = e.updated_parsed

                if pub:
                    pub_iso = datetime(*pub[:6]).isoformat()
                else:
                    pub_iso = datetime.utcnow().isoformat()

                items.append({
                    "id": make_id(link),
                    "title": title,
                    "link": link,
                    "description": summary,
                    "pubDate": pub_iso
                })

            except Exception as e:
                print("❌ Item error:", e)
                continue

    print("Fetched total:", len(items))
    return items


# 🎯 filter
def filter_items(items, min_score):
    out = []

    for i in items:
        text = (i["title"] + " " + i["description"]).lower()

        if "stolperstein" not in text:
            continue

        if score(text) >= min_score:
            out.append(i)

    return out


# 🗂 archief update
def update_archive(new_items, archive):
    existing = {i.get("link") for i in archive}

    for item in new_items:
        if item["link"] not in existing:
            archive.append(item)

    cutoff = datetime.utcnow() - timedelta(days=MAX_DAYS)

    cleaned_archive = []
    for i in archive:
        try:
            if "id" not in i:
                i["id"] = make_id(i["link"])

            if datetime.fromisoformat(i["pubDate"]) > cutoff:
                cleaned_archive.append(i)
        except Exception as e:
            print("❌ Archive item skipped:", e)

    return cleaned_archive


# 📡 RSS build
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

        # 🔥 FIX: altijd guid beschikbaar
        guid = i.get("id") or make_id(i["link"])

        rss_items += f"""
        <item>
          <title><![CDATA[{i['title']}]]></title>
          <link>{i['link']}</link>
          <guid>{guid}</guid>
          <description><![CDATA[{i['description']}]]></description>
          <pubDate>{pubdate}</pubDate>
        </item>
        """

    build_time = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>Stolpersteine News</title>
<link>https://jandewit6.github.io/stolpersteine-feed/</link>
<description>WWII-related Stolpersteine news</description>
<lastBuildDate>{build_time}</lastBuildDate>
{rss_items}
</channel>
</rss>
"""


# ▶️ main
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
        print("⚠️ fallback: using raw items")
        selected = fetched[:20]

    archive = update_archive(selected, archive)
    archive.sort(key=lambda x: x["pubDate"], reverse=True)

    save_archive(archive)

    rss = build_rss(archive)

    with open(FEED_FILE, "w", encoding="utf-8") as f:
        f.write(rss)

    print("✅ feed.xml written")


# 🧪 debug wrapper
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("❌ FATAL ERROR:", e)
        traceback.print_exc()
        raise
