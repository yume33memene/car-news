#!/usr/bin/env python3
# japanese_car_news_line_flex.py
# requirements: feedparser, requests, beautifulsoup4

import os
import json
import time
import feedparser
import requests
from bs4 import BeautifulSoup

# --------------------
# 設定
# --------------------
LINE_TOKEN = os.getenv("LINE_CHANNEL_TOKEN")
SENT_FILE = "sent_ids.json"
MAX_POSTS_PER_RUN = 3   # Flexは情報量が多いので少数推奨

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

# デフォルトサムネイル（og:imageが無い場合に使用）
# 実運用ではあなたの公開ホスティング（GitHub rawなど）URLに置き換えてください
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


def short(text, n=200):
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

# --------------------
# Flex の作成（問題になりにくい安全な構造）
# --------------------

def make_flex_bubble(title, brand, link, image_url=None, is_gr86=False):
    """
    LINE Flex の bubble を簡潔で確実な構造にする。
    """
    color_accent = "#E74C3C" if is_gr86 else "#2D9CDB"
    img = image_url or DEFAULT_IMAGE

    bubble = {
        "type": "bubble",
        "hero": {
            "type": "image",
            "url": img,
            "size": "full",
            "aspectRatio": "16:9",
            "aspectMode": "cover"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": ("$D83D$DD25 GR86速報：" if is_gr86 else f"【{brand}】") + title,
                    "wrap": True,
                    "weight": "bold",
                    "size": "md"
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "md",
                    "contents": [
                        {
                            "type": "text",
                            "text": brand or "（不明）",
                            "size": "sm",
                            "color": color_accent,
                            "weight": "bold"
                        }
                    ]
                }
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {
                    "type": "button",
                    "style": "link",
                    "height": "sm",
                    "action": {
                        "type": "uri",
                        "label": "記事を開く",
                        "uri": link
                    }
                }
            ]
        }
    }
    return bubble


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
# LINE送信: Flex
# --------------------

def send_flex_messages(flex_contents):
    if not LINE_TOKEN:
        print("$274C LINE_CHANNEL_TOKEN 未設定")
        return False
    url = "https://api.line.me/v2/bot/message/broadcast"
    headers = {"Content-Type":"application/json", "Authorization":f"Bearer {LINE_TOKEN}"}
    messages = []
    for bubble in flex_contents:
        alt = bubble.get("body", {}).get("contents", [{}])[0].get("text", "ニュース")
        messages.append({
            "type":"flex",
            "altText": alt[:60],
            "contents": bubble
        })
    payload = {"messages": messages}
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        if r.status_code in (200,201):
            print("$2705 LINE flex broadcast success")
            return True
        else:
            print("$26A0$FE0F LINE API error:", r.status_code, r.text)
            return False
    except Exception as e:
        print("$274C send exception:", e)
        return False


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
        title = e.get("title", "")
        summary = (e.get("summary") or e.get("description") or "") or ""
        brand = detect_brand(title, summary)
        gr86 = is_gr86_text(title, summary)
        if not brand and not gr86:
            continue
        link = e.get("link", "")
        candidates.append((gr86, brand or "（不明）", uid, title, summary, link))

    # GR優先
    candidates.sort(key=lambda x: (0 if x[0] else 1))
    to_send = candidates[:MAX_POSTS_PER_RUN]
    print("send candidates:", len(to_send))
    if not to_send:
        print("$2705 0件送信完了")
        return

    bubbles = []
    for gr86, brand, uid, title, summary, link in to_send:
        img = fetch_og_image(link) or DEFAULT_IMAGE
        bubble = make_flex_bubble(title, brand, link, image_url=img, is_gr86=gr86)
        bubbles.append(bubble)
        new_sent.add(uid)

    ok = send_flex_messages(bubbles)
    if ok:
        save_sent_ids(new_sent)
        print(f"$2705 {len(bubbles)}件送信完了")
    else:
        print("$274C LINE送信失敗")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("実行エラー:", e)
