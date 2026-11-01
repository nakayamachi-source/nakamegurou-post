#!/usr/bin/env python3
"""posts.json の status が "scheduled" で、予約時刻を過ぎた投稿を Instagram に投稿する。

環境変数: IG_USER_ID, IG_ACCESS_TOKEN, (任意) GITHUB_REPOSITORY, GITHUB_REF_NAME
--dry-run で投稿せず対象だけ表示する。
status: draft(投稿しない) -> scheduled(予約済み) -> posted / error
"""
import json, os, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone

GRAPH = "https://graph.facebook.com/v21.0"
PATH = os.path.join(os.path.dirname(__file__), "posts.json")


def call(url, data=None):
    body = urllib.parse.urlencode(data).encode() if data else None
    with urllib.request.urlopen(urllib.request.Request(url, data=body)) as r:
        return json.load(r)


def image_url(p):
    if p.startswith("http"):
        return p
    repo = os.environ["GITHUB_REPOSITORY"]
    ref = os.environ.get("GITHUB_REF_NAME", "main")
    return f"https://raw.githubusercontent.com/{repo}/{ref}/{urllib.parse.quote(p)}"


def publish(post, uid, token):
    c = call(f"{GRAPH}/{uid}/media", {
        "image_url": image_url(post["image"]),
        "caption": post["caption"],
        "access_token": token})
    for _ in range(10):  # コンテナ処理待ち
        s = call(f"{GRAPH}/{c['id']}?fields=status_code&access_token={token}")
        if s.get("status_code") == "FINISHED":
            break
        if s.get("status_code") == "ERROR":
            raise RuntimeError("container error")
        time.sleep(3)
    return call(f"{GRAPH}/{uid}/media_publish",
                {"creation_id": c["id"], "access_token": token})["id"]


def main():
    dry = "--dry-run" in sys.argv
    posts = json.load(open(PATH, encoding="utf-8"))
    now = datetime.now(timezone.utc)
    due = [p for p in posts if p["status"] == "scheduled"
           and datetime.fromisoformat(p["scheduled_at"]) <= now]
    for p in due:
        print(("[dry-run] " if dry else "") + "投稿対象:", p["id"])
        if dry:
            continue
        try:
            p["media_id"] = publish(p, os.environ["IG_USER_ID"], os.environ["IG_ACCESS_TOKEN"])
            p["status"] = "posted"
        except Exception as e:
            p["status"], p["error"] = "error", str(e)
            print("失敗:", p["id"], e, file=sys.stderr)
    if due and not dry:
        json.dump(posts, open(PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        open(PATH, "a").write("\n")
    if not due:
        print("投稿対象なし")


main()
