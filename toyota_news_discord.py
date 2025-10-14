#!/usr/bin/env python3
# japanese_car_news_colored.py
# requirements: feedparser, requests, beautifulsoup4
# (注) いすゞ / 日野 / 三菱ふそう のブランド・RSSは除外済み

import os
import json
import time
import hashlib
import feedparser
import requests
from bs4 import BeautifulSoup

# -----------------------
# 設定
# -----------------------
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK")  # GitHub Secrets に登録済みのものを使用
SENT_FILE = "sent_ids.json"
MAX_POSTS_PER_RUN = 8  # 一回の実行でDiscordに投げる最大embed数（Webhookの制限に注意）

# -----------------------
# ブランド => カラー(hex) マップ（指定の3社を除外済み）
# -----------------------
BRAND_COLORS = {
    "トヨタ": 0xE60012,        # トヨタ赤
    "レクサス": 0xD4AF37,      # ゴールド風
    "GR": 0xE74C3C,            # GR系は赤寄り
    "GR86": 0xE74C3C,          # GR86は特別扱い（赤）
    "ホンダ": 0x1E90FF,        # 青
    "日産": 0xFF4500,          # オレンジ系
    "マツダ": 0x8B0000,        # 濃赤
    "スバル": 0x0033A0,        # スバル青
    "三菱": 0x990000,
    "スズキ": 0x0066CC,
    "ダイハツ": 0xFF0000,
    # メディア系（バックアップ）
    "Car Watch": 0x666666,
    "ベストカー": 0x666666,
}

# キーワード判定に使うブランドキーワードリスト（BRAND_COLORS のキーから生成）
BRAND_KEYWORDS = [k for k in BRAND_COLORS.keys()]

# -----------------------
# ユーティリティ
# -----------------------
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

def short(text, n=220):
    if not text:
        return ""
    t = " ".join(text.split())
    return (t[: n - 1] + "…") if len(t) > n else t

def fetch_og_image(url):
    """OGP画像を取得（可能なら）"""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, timeout=6, headers=headers)
        if r.status_code != 200:
            return None
        from bs4 import BeautifulSoup as _BS
        soup = _BS(r.text, "html.parser")
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
    """タイトル＋要約からブランドを検出（最初に見つけたブランドを返す）"""
    text = (title + " " + summary).lower()
    for k in BRAND_KEYWORDS:
        if k.lower() in text:
            return k
    return None

def is_gr86_text(title, summary=""):
    t = (title + " " + summary).lower()
    if "gr86" in t.replace(" ", "") or "gr-86" in t or "ＧＲ８６" in title or "GR86" in title:
        return True
    if "86" in t and "gr" in t:
        return True
    return False

# -----------------------
# RSSフィード一覧（指定3社のRSSは除外済み）
# -----------------------
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

    # 自動車メディア（補助）
    "https://car.watch.impress.co.jp/docs/common/rss.xml",
    "https://bestcarweb.jp/rss",
]

# -----------------------
# Discord投稿処理
# -----------------------
def make_embed_obj(title, link, brand=None, summary="", image=None, is_gr86=False):
    # 色の決定
    color = BRAND_COLORS.get(brand, 0x2D9CDB) if brand else 0x2D9CDB
    if is_gr86:
        color = BRAND_COLORS.get("GR86", color)

    desc = short(summary, 260)
    embed = {
        "title": ("🔥 GR86速報： " if is_gr86 else "") + title,
        "url": link,
        "description": desc,
        "color": color,
        "fields": [
            {"name": "ブランド", "value": brand or "（不明）", "inline": True},
        ],
    }
    if image:
        embed["image"] = {"url": image}
    return embed

def post_embeds_to_discord(embeds):
    if not WEBHOOK_URL:
        print("❌ DISCORD_WEBHOOK が未設定です（Secretsに登録してください）")
        return False
    payload = {"embeds": embeds}
    try:
        r = requests.post(WEBHOOK_URL, json=payload, timeout=10)
        if r.status_code in (200, 204):
            return True
        else:
            print("⚠️ Discord投稿エラー:", r.status_code, r.text)
            return False
    except Exception as e:
        print("❌ Discord送信例外:", e)
        return False

# -----------------------
# メイン処理
# -----------------------
def fetch_all_entries():
    entries = []
    seen_links = set()
    for url in RSS_URLS:
        try:
            feed = feedparser.parse(url)
            if hasattr(feed, "entries"):
                for en in feed.entries:
                    link = en.get("link") or en.get("id") or ""
                    if not link:
                        continue
                    if link in seen_links:
                        continue
                    seen_links.add(link)
                    entries.append(en)
        except Exception as e:
            print("RSS取得エラー:", url, e)
    return entries

def main():
    sent = load_sent_ids()
    new_sent = set(sent)

    entries = fetch_all_entries()
    print(f"取得エントリ数: {len(entries)}")

    candidates = []
    for en in entries:
        uid = en.get("id", en.get("link"))
        if not uid or uid in sent:
            continue
        title = en.get("title", "") or ""
        summary = (en.get("summary") or en.get("description") or "") or ""
        brand = detect_brand(title, summary)
        gr86 = is_gr86_text(title, summary)
        if not brand and not gr86:
            continue
        link = en.get("link", "")
        candidates.append((gr86, brand or "（不明）", uid, title, summary, link))

    candidates.sort(key=lambda x: (0 if x[0] else 1))

    to_send = candidates[:MAX_POSTS_PER_RUN]
    print(f"送信候補数: {len(to_send)}")

    embeds_batch = []
    for gr86, brand, uid, title, summary, link in to_send:
        image = fetch_og_image(link)
        embed = make_embed_obj(title, link, brand=brand, summary=summary, image=image, is_gr86=gr86)
        embeds_batch.append(embed)
        new_sent.add(uid)

    if embeds_batch:
        ok = post_embeds_to_discord(embeds_batch)
        if ok:
            save_sent_ids(new_sent)
            print(f"✅ {len(embeds_batch)}件送信完了")
        else:
            print("❌ Discord投稿に失敗しました")
    else:
        print("✅ 0件送信完了（新着なしまたは対象外）")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("実行時エラー:", e)
