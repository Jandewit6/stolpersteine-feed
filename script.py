import feedparser
from datetime import datetime, timedelta
import re
import hashlib
import json
import os

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
    "nazi": 3, "nazis": 3,
    "world war ii": 3, "wwii": 3,
    "second world war": 3,
    "zweiter weltkrieg": 3,

    "deport": 2, "deportation": 2, "deportiert": 2,
    "jew": 2, "jewish": 2, "jude": 2,

    "victim": 2, "opfer": 2,
    "memorial": 2, "gedenk": 2,
    "commemoration": 2, "erinner": 2,
    "remembrance": 2,

    "auschwitz": 3,
    "genocide": 3,
    "ghetto": 2,
    "persecution": 2, "verfolg": 2
}

NEGATIVE = [
    "football", "soccer", "club",
    "restaurant", "recipe", "festival",
    "music", "band", "real estate"
]

MIN_SCORE = 5


def score(text):
    text = text.lower()
    s = 0

    for w, val in CONTEXT.items():
        if w in text:
            s += val

    for w in NEGATIVE:
        if w in text:
            s -= 3

    return s


def relevant(item):
    text = (item["title"] + item["summary"]).lower()

    if "stolperstein" not in text:
        return False

    if score(text) < MIN_SCORE:
        return False

    return True


def clean(text):
    text = re.sub("<.*?>", "", text)
    text = text.replace("\n", " ").strip()
    return text[:500]


def make_id(item):
    base = (item["title"] + item["link"]).lower()
    return hashlib.md5(base.encode()).hexdigest()


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
            if not e.get("published_parsed"):
                continue

            items.append({
                "id": make_id(e),
                "title": clean(e.get("title", "")),
                "link": e.get("link", ""),
                "description": clean(e.get("summary", "")),
                "pubDate": datetime(*e.published_parsed[:6]).isoformat()
            })

    return items


def update_archive(new_items, archive):
    existing_ids = {i["id"] for i in archive}

    for item in new_items:
        if item["id"] not in existing_ids:
            archive.append(item)

    cutoff = datetime.utcnow() - timedelta(days=MAX_DAYS)

    archive = [
        i for i in archive
        if datetime.fromisoformat(i["pubDate"]) > cutoff
    ]

    return archive


def build_rss(items):
    rss_items = ""

    for i in items[:30]:
        pubdate = datetime.fromisoformat(i["pubDate"]).strftime("%a, %d %b %Y %H:%M:%S GMT")

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
<description>Filtered WWII-related Stolpersteine news (1 year archive)</description>
{rss_items}
</channel>
</rss>
"""


def main():
    archive = load_archive()
    fetched = fetch()

    filtered = [i for i in fetched if relevant(i)]

    archive = update_archive(filtered, archive)

    archive.sort(key=lambda x: x["pubDate"], reverse=True)

    save_archive(archive)

    rss = build_rss(archive)

    with open("feed.xml", "w", encoding="utf-8") as f:
        f.write(rss)


if __name__ == "__main__":
    main()
