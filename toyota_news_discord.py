import os
import feedparser
import requests
import json
from datetime import datetime

# Webhook URL (GitHub Secrets で設定)
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK")

# ニュース対象ブランド
BRANDS = ["トヨタ", "GR86", "スバル", "日産", "ホンダ"]

# 記事ID管理ファイル
SENT_IDS_FILE = "sent_ids.json"


def load_sent_ids():
    """送信済み記事IDを読み込み"""
    if not os.path.exists(SENT_IDS_FILE):
        return set()
    with open(SENT_IDS_FILE, "r", encoding="utf-8") as f:
        try:
            return set(json.load(f))
        except json.JSONDecodeError:
            return set()


def save_sent_ids(sent_ids):
    """送信済み記事IDを保存"""
    with open(SENT_IDS_FILE, "w", encoding="utf-8") as f:
        json.dump(list(sent_ids), f, ensure_ascii=False, indent=2)


def fetch_toyota_news():
    """トヨタ公式ニュースRSSから記事を取得"""
    feeds = [
        "https://global.toyota/jp/newsroom/rss",
        "https://toyotagazooracing.com/jp/rss.xml",
    ]
    entries = []
    for url in feeds:
        feed = feedparser.parse(url)
        entries.extend(feed.entries)
    return entries


def make_embed(entry):
    """Discord用Embedデータを作成"""
    title = entry.title
    link = entry.link
    date = entry.published if "published" in entry else ""
    summary = entry.summary[:150] + "..." if "summary" in entry else ""
    embed = {
        "title": title,
        "url": link,
        "description": summary,
        "color": 0xE60012,  # トヨタ赤
        "footer": {"text": date},
    }
    return embed


def post_to_discord(embed):
    """Discordに投稿"""
    payload = {"embeds": [embed]}
    response = requests.post(WEBHOOK_URL, json=payload)
    if response.status_code != 204:
        print("⚠️ Discord投稿エラー:", response.status_code, response.text)


def main():
    sent_ids = load_sent_ids()
    new_sent_ids = set(sent_ids)

    entries = fetch_toyota_news()

    for entry in entries:
        uid = entry.get("id", entry.get("link"))
        if uid in sent_ids:
            continue

        title = entry.get("title", "")
        if not any(keyword in title for keyword in BRANDS):
            continue

        embed = make_embed(entry)
        post_to_discord(embed)
        new_sent_ids.add(uid)

    save_sent_ids(new_sent_ids)
    print(f"✅ 投稿完了 {len(new_sent_ids) - len(sent_ids)} 件")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("❌ エラー発生:", e)
