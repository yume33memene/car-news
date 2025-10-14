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
MAX_POSTS_PER_RUN = 3 # Flexは情報量が多いので少数推奨


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


print("実行エラー:", e)
