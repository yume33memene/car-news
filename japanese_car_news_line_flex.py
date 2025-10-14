#!/usr/bin/env python3
# japanese_car_news_line_text_batched.py
# requirements: feedparser, requests, beautifulsoup4

import os
import json
import time
import feedparser
import requests
from urllib.parse import urlparse
from datetime import datetime

# --------------------
# 設定
# --------------------
LINE_TOKEN = os.getenv("LINE_CHANNEL_TOKEN")
SENT_FILE = "sent_ids.json"

# 収集・配信件数（柔軟に調整可）
MAX_POSTS_PER_RUN = 50               # まとめて拾い、あとで文字数で安全分割
MAX_UNITS_PER_TEXT = 4800            # 安全側に5,000未満で分割（UTF-16コード単位）
MAX_MSG_OBJECTS_PER_REQUEST = 5      # LINEの1リクエスト上限（仕様）
SLEEP_BETWEEN_REQUESTS = 0.8         # 連続broadcastの間隔（レート制限配慮）

BRANDS = [
    "トヨタ", "レクサス", "GR", "GR86",
    "ホンダ", "アキュラ",
    "日産", "ニスモ",
    "マツダ",
    "スバル", "STI",
    "三菱","RALLIART",
    "スズキ",
    "ダイハツ",
]

RSS_URLS = [
    "https://global.toyota/export/jp/allnews_rss.xml",
    "https://global.toyota/jp/newsroom/toyota/rss.xml",
    "https://global.toyota/jp/newsroom/lexus/rss.xml",
    "https://toyotagazooracing.com/jp/rss.xml",
    "https://www.honda.co.jp/rss/",
    "https://global.nissannews.com/ja-JP/rss",
    "https://newsroom.mazda.com/ja_JP/rss.xml",
    "https://www.subaru.co.jp/news/rss.xml",
    "https://www.mitsubishi-motors.com/jp/newsrelease/rss.xml",
    "https://www.suzuki.co.jp/release/rss.xml",
    "https://www.daihatsu.co.jp/news/rss.xml",
    "https://car.watch.impress.co.jp/docs/common/rss.xml",
    "https://bestcarweb.jp/rss",
]

# --------------------
# ユーティリティ
# --------------------
def load_sent_ids():
    if not os.path.exists(SENT_FILE):
        return set()
    try:
        with open(SENT_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return set()

def save_sent_ids(s):
    with open(SENT_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(list(s)), f, ensure_ascii=False, indent=2)

def detect_brand(title, summary=""):
    text = (title + " " + summary).lower()
    for b in BRANDS:
        if b.lower() in text:
            return b
    return None

def is_gr86_text(title, summary=""):
    t = (title + " " + summary).lower()
    if "gr86" in t.replace(" ", "") or "gr-86" in t:
        return True
    if "86" in t and "gr" in t:
        return True
    return False

def domain_of(url):
    try:
        return urlparse(url).netloc
    except Exception:
        return ""

# --- UTF-16コード単位での文字数カウント（LINE仕様準拠） ---
def utf16_units(s: str) -> int:
    # UTF-16-LE変換のバイト長 / 2 = コード単位数
    return len(s.encode("utf-16-le")) // 2

# --------------------
# RSS取得
# --------------------
def fetch_all_entries():
    entries = []
    seen_links = set()
    for url in RSS_URLS:
        try:
            feed = feedparser.parse(url)
            if hasattr(feed, "entries"):
                for e in feed.entries:
                    link = e.get("link") or e.get("id") or ""
                    if not link or link in seen_links:
                        continue
                    seen_links.add(link)
                    entries.append(e)
        except Exception as ex:
            print("RSS error:", url, ex)
    return entries

# --------------------
# テキスト生成（題名・公開日・URLのみ／超シンプル）
# --------------------
def render_item(title, pub, link):
    # できるだけ見やすく・短く
    pub_txt = pub or ""
    lines = [
        f"題名: {title}",
        f"公開日: {pub_txt}",
        f"URL: {link}",
    ]
    return "\n".join(lines)

def build_text_messages(items, max_units=MAX_UNITS_PER_TEXT):
    """
    items: [(title, pub, link), ...]
    UTF-16単位の上限内で複数のテキストメッセージに安全分割。
    """
    messages = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    header = f"自動車ニュース速報（{now}）\n\n"
    cur = header

    for (title, pub, link) in items:
        block = render_item(title, pub, link) + "\n" + ("-" * 20) + "\n"
        if utf16_units(cur + block) <= max_units:
            cur += block
        else:
            messages.append(cur.strip())
            cur = header + block

    if cur.strip():
        messages.append(cur.strip())
    return messages

# --------------------
# LINE送信（/broadcastを5件ずつバッチ）
# --------------------
def post_broadcast(message_objs):
    if not LINE_TOKEN:
        print("❌ LINE_CHANNEL_TOKEN 未設定")
        return False
    url = "https://api.line.me/v2/bot/message/broadcast"
    headers = {"Content-Type":"application/json", "Authorization":f"Bearer {LINE_TOKEN}"}
    payload = {"messages": message_objs}
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=20)
        if r.status_code in (200,201):
            print("✅ broadcast success:", len(message_objs))
            return True
        else:
            print("⚠️ LINE API error:", r.status_code, r.text)
            return False
    except Exception as e:
        print("❌ send exception:", e)
        return False

def send_broadcast_in_batches(texts, batch_size=MAX_MSG_OBJECTS_PER_REQUEST):
    ok_all = True
    for i in range(0, len(texts), batch_size):
        chunk = texts[i:i+batch_size]
        message_objs = [{"type":"text","text":t} for t in chunk]  # テキストのみ
        ok = post_broadcast(message_objs)
        ok_all = ok_all and ok
        time.sleep(SLEEP_BETWEEN_REQUESTS)
    return ok_all

# --------------------
# main
# --------------------
def main():
    sent = load_sent_ids()
    new_sent = set(sent)
    entries = fetch_all_entries()
    print("entries:", len(entries))

    # 抽出（重複排除＆ブランド・GR86関連のみ）
    candidates = []
    for e in entries:
        uid = e.get("id", e.get("link"))
        if not uid or uid in sent:
            continue

        title = e.get("title", "") or ""
        summary = (e.get("summary") or e.get("description") or "") or ""
        brand = detect_brand(title, summary)
        gr86 = is_gr86_text(title, summary)
        if not brand and not gr86:
            continue

        link = e.get("link", "")
        pub = e.get("published") or e.get("updated") or ""
        candidates.append((gr86, title, pub, link, uid))

    # GR/GR86優先
    candidates.sort(key=lambda x: (0 if x[0] else 1))

    # 上限まで選択
    picked = candidates[:MAX_POSTS_PER_RUN]
    print("picked:", len(picked))
    if not picked:
        print("✅ 0件送信完了")
        return

    # テキスト化（題名・公開日・URLのみ）
    items = [(c[1], c[2], c[3]) for c in picked]
    texts = build_text_messages(items, max_units=MAX_UNITS_PER_TEXT)

    # 5件ずつバッチで /broadcast
    ok = send_broadcast_in_batches(texts, batch_size=MAX_MSG_OBJECTS_PER_REQUEST)
    if ok:
        for c in picked:
            new_sent.add(c[4])
        save_sent_ids(new_sent)
        print(f"✅ {len(texts)}メッセージ送信（合計{len(picked)}記事）完了")
    else:
        print("❌ LINE送信失敗")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("実行エラー:", e)
