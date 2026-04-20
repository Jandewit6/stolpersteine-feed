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

FEEDS = [
    "https://news.google.com/rss/search?q=stolpersteine&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=stolpersteine&hl=de&gl=DE&ceid=DE:de",
    "https://www.stolpersteine.eu/feed/"
]

STRICT_SCORE = 3


# 🔍 DEBUG HELPER
def debug_print(label, text):
    print(f"\n--- {label} ---")
    print(text[:300])


# 🧹 CLEAN (extra agressief)
def clean(text):
    if not text:
        return ""

    original = text

    text = re.sub("<.*?>", "", text)

    for _ in range(2):
        text = html.unescape(text)

    # 🔥 HARD ENTITY REMOVAL
    if "&" in text:
        debug_print("ENTITY BEFORE CLEAN", text)

    text = re.sub(r"&[^ ]+;", " ", text)

    # fallback: kill any remaining &
    text = text.replace("&", " and ")

    text = re.sub(r"[\x00-\x1F\x7F]", "", text)

    text = re.sub(r"\s+", " ", text).strip()

    if "&" in text:
        debug_print("ENTITY AFTER CLEAN", text)

    return text[:500]


# 🧠 SIMPELE SAMENVATTING
def summarize(text):
    text = clean(text)
    sentences = re.split(r'(?<=[.!?]) +', text)
    return " ".join(sentences[:2])[:300]


def make_id(title, link):
    return hashlib.md5((title + link).lower().encode()).hexdigest()


def fetch():
    items = []

    for url in FEEDS:
        print(f"\nFetching: {url}")
        feed = feedparser.parse(url)

        for e in feed.entries:
            title = e.get("title", "")
            summary = e.get("summary", "")
            link = e.get("link", "")

            debug_print("RAW TITLE", title)
            debug_print("RAW SUMMARY", summary)

            cleaned_title = clean(title)
            cleaned_summary = summarize(summary)

            debug_print("CLEAN TITLE", cleaned_title)
            debug_print("CLEAN SUMMARY", cleaned_summary)

            items.append({
                "id": make_id(title, link),
                "title": cleaned_title,
                "link": link,
                "description": cleaned_summary,
                "pubDate": datetime.now().isoformat()
            })

    return items


# 🧪 XML VALIDATOR PER ITEM
def test_item_xml(item):
    test_xml = f"""
    <item>
      <title>{item['title']}</title>
      <description>{item['description']}</description>
    </item>
    """
    try:
        ET.fromstring(test_xml)
        return True
    except Exception as e:
        print("\n❌ BROKEN ITEM:")
        print(item)
        print("ERROR:", e)
        return False


# 📡 BUILD RSS (skip kapotte items)
def build_rss(items):
    rss_items = ""

    valid_count = 0

    for i in items:
        if not test_item_xml(i):
            print("⛔ Skipping broken item")
            continue

        valid_count += 1

        rss_items += f"""
        <item>
          <title><![CDATA[{i['title']}]]></title>
          <link>{i['link']}</link>
          <description><![CDATA[{i['description']}]]></description>
          <pubDate>{datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT")}</pubDate>
        </item>
        """

    print(f"\n✅ Valid items: {valid_count}")

    return f"""<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
<channel>
<title>DEBUG Stolpersteine Feed</title>
<link>https://jandewit6.github.io/stolpersteine-feed/</link>
<description>Debug version</description>
{rss_items}
</channel>
</rss>
"""


def main():
    items = fetch()

    rss = build_rss(items)

    print("\n--- FINAL RSS PREVIEW ---")
    print(rss[:1000])

    with open(FEED_FILE, "w", encoding="utf-8") as f:
        f.write(rss)


if __name__ == "__main__":
    main()
