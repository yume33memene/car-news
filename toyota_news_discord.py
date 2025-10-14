#!/usr/bin/env python3
d = feedparser.parse(feed_url)
except Exception as e:
print("feed parse err:", e)
continue
for entry in d.entries[:12]:
eid = entry_id(entry)
if eid in sent:
continue
text_blob = " ".join([entry.get("title",""), entry.get("summary","") or ""])
is_gr = is_gr86_text(text_blob)
embed = make_embed(entry, brand, is_gr)
to_post_embeds.append((is_gr, eid, embed))


# 優先度：GR86 を先に並べる
to_post_embeds.sort(key=lambda x: (0 if x[0] else 1))


# Discord は一度に最大10 embeds（Webhook制限）なので分割して投げる
batched = []
batch = []
for _, eid, emb in to_post_embeds:
batch.append((eid, emb))
if len(batch) >= 8:
batched.append(batch)
batch = []
if batch: batched.append(batch)


any_sent = False
for batch in batched:
embeds = [b for (_, b) in batch]
ok = post_to_discord(embeds)
if ok:
for eid, _ in batch:
sent.add(eid)
any_sent = True
time.sleep(1.2)


if any_sent:
save_sent(sent)
# commit sent_ids.json back to repo using GITHUB_TOKEN (available in Actions)
gh_token = os.environ.get("GITHUB_TOKEN")
repo = os.environ.get("GITHUB_REPOSITORY") # owner/repo
if gh_token and repo:
try:
subprocess.run(["git", "config", "user.email", "actions@github.com"], check=True)
subprocess.run(["git", "config", "user.name", "github-actions"], check=True)
subprocess.run(["git", "add", SENT_FILE], check=True)
subprocess.run(["git", "commit", "-m", "Update sent_ids.json by workflow"], check=True)
push_url = f"https://x-access-token:{gh_token}@github.com/{repo}.git"
subprocess.run(["git", "push", push_url, "HEAD:refs/heads/main"], check=True)
print("Committed sent_ids.json")
except Exception as e:
print("Git commit/push error:", e)


if __name__ == "__main__":
main()