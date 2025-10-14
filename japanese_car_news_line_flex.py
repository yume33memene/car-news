#!/usr/bin/env python3
# japanese_car_news_line_text_broadcast.py
# requirements: feedparser, requests, beautifulsoup4

import os
import json
import time
import feedparser
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from datetime import datetime

# --------------------
# 設定
# --------------------
LINE_TOKEN = os.getenv("LINE_CHANNEL_TOKEN")
SENT_FILE = "sent_ids.json"

# できるだけ多く届けたい前提で増やす（過剰配信はプランや月間上限に注意）
MAX_POSTS_PER_RUN = 30

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

# og:image 取得は残してもテキスト主体なので未使用（必要なら本文へURL掲載でも可）
DEFAULT_IMAGE = "https://raw.githubusercontent.com/your-username/your-repo/main/assets/default_card.jpg"

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

def short(text, n=800):
    if not text:
        return ""
    t = " ".join(text.split())
    return (t[: n - 1] + "…") if len(t) > n else t

def fetch_og_image(url):
    try:
        r = requests.get(url, timeout=6, headers={"User-Agent":"Mozilla/5.0"})
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            return og["content"]
        tc = soup.find("meta", attrs={"name":"twitter:image"})
        if tc and tc.get("content"):
            return tc["content"]
    except Exception:
        return None
    return None

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

# --- UTF-16のコード単位数を正確に数える（LINEの文字数上限対策） ---
def utf16_units(s: str) -> int:
    # UTF-16-LEに変換したバイト長 / 2 がコード単位数
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
# テキスト生成
# --------------------
def render_item(gr86, brand, title, summary, link, pub):
    # 絵文字は上限超過の原因になり得るため使用しない（安全運用）
    lines = []
    head = f"[{brand}] {title}"
    lines.append(head)
    if pub:
        try:
            # pub は文字列のことがあるのでそのまま表示
            lines.append(f"公開日: {pub}")
        except Exception:
            pass
    dom = domain_of(link)
    if summary:
        lines.append(f"概要: {short(summary, n=800)}")
    lines.append(f"URL: {link}")
    if dom:
        lines.append(f"ソース: {dom}")
    return "\n".join(lines)

def build_text_messages(items, max_units_per_message=4800):
    """
    items: [(gr86, brand, title, summary, link, pub), ...]
    できるだけ多くの記事を1メッセージに詰め、UTF-16単位の上限内で分割。
    """
    messages = []
    current = []
    # ヘッダー（日時付き）
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    header = f"自動車ニュースまとめ（{now}）\n"
    cur_text = header
    for it in items:
        block = render_item(*it)
        # 区切り線
        block = block + "\n" + ("-" * 24) + "\n"
        # 追加した場合の長さを見積もり
        if utf16_units(cur_text + block) <= max_units_per_message:
            cur_text += block
        else:
            # 現在のメッセージを確定
            messages.append(cur_text.strip())
            # 新しいメッセージを開始
            cur_text = header + block
    if cur_text.strip():
        messages.append(cur_text.strip())
    return messages

# --------------------
# LINE送信: テキスト（broadcast）
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
            print("✅ LINE text broadcast success")
            return True
        else:
            print("⚠️ LINE API error:", r.status_code, r.text)
            return False
    except Exception as e:
        print("❌ send exception:", e)
        return False

def send_text_messages(texts):
    """
    LINEは1リクエストで最大5メッセージまで送れるため分割して送る。
    """
    chunk = 5
    ok_all = True
    for i in range(0, len(texts), chunk):
        batch = texts[i:i+chunk]
        message_objs = [{"type":"text","text":t} for t in batch]
        ok = post_broadcast(message_objs)
        ok_all = ok_all and ok
        time.sleep(0.8)  # 軽い間隔を空ける（レート制限配慮）
    return ok_all

# --------------------
# main
# --------------------
def main():
    sent = load_sent_ids()
    new_sent = set(sent)
    entries = fetch_all_entries()
    print("entries:", len(entries))

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
        candidates.append((gr86, brand or "（不明）", title, summary, link, pub, uid))

    # GR/GR86優先
    candidates.sort(key=lambda x: (0 if x[0] else 1))

    # 送信対象を絞る（必要に応じて増減）
    to_send = candidates[:MAX_POSTS_PER_RUN]
    print("send candidates:", len(to_send))
    if not to_send:
        print("✅ 0件送信完了")
        return

    # テキスト化（uidは別管理）
    items = [(c[0], c[1], c[2], c[3], c[5], c[4]) for c in to_send]  # (gr86, brand, title, summary, pub, link) に並べ替え
    texts = build_text_messages(items)

    ok = send_text_messages(texts)
    if ok:
        for c in to_send:
            new_sent.add(c[6])  # uid追加
        save_sent_ids(new_sent)
        print(f"✅ {len(texts)}メッセージ送信完了 / {len(to_send)}記事")
    else:
        print("❌ LINE送信失敗")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("実行エラー:", e)
