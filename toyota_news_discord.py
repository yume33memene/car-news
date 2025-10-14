import os
import feedparser
import requests
import json

WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK")
SENT_IDS_FILE = "sent_ids.json"

# ブランドフィルタ（GR86など）
BRANDS = ["トヨタ", "GR86", "スバル", "日産", "ホンダ"]

def load_sent_ids():
    """送信済み記事IDをロード"""
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

def fetch_feeds():
    """トヨタ・GR公式RSSを取得"""
    urls = [
        "https://global.toyota/jp/newsroom/rss",
        "https://toyotagazooracing.com/jp/rss.xml",
    ]
    entries = []
    for url in urls:
        feed = feedparser.parse(url)
        entries.extend(feed.entries)
    return entries

def make_embed(entry):
    """Discord向けカード整形"""
    title = entry.get("title", "（タイトルなし）")
    link = entry.get("link", "")
    date = entry.get("published", "")
    summary = entry.get("summary", "")
    return {
        "title": title,
        "url": link,
        "description": summary[:150] + "...",
        "color": 0xE60012,
        "footer": {"text": date},
    }

def post_to_discord(embed):
    """Discordへ送信"""
    if not WEBHOOK_URL:
        raise ValueError("❌ DISCORD_WEBHOOK が設定されていません")
    response = requests.post(WEBHOOK_URL, json={"embeds": [embed]})
    if response.status_code != 204:
        print("⚠️ Discord送信失敗:", response.status_code, response.text)

def main():
    sent_ids = load_sent_ids()
    new_sent_ids = set(sent_ids)
    entries = fetch_feeds()

    for e in entries:
        uid = e.get("id", e.get("link"))
        if not uid or uid in sent_ids:
            continue

        title = e.get("title", "")
        if not any(b in title for b in BRANDS):
            continue

        embed = make_embed(e)
        post_to_discord(embed)
        new_sent_ids.add(uid)

    save_sent_ids(new_sent_ids)
    print(f"✅ {len(new_sent_ids) - len(sent_ids)}件送信完了")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("❌ 実行エラー:", e)
