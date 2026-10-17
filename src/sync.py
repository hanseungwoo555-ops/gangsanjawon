# -*- coding: utf-8 -*-
"""네이버 블로그와 인스타그램에서 최신 글·영상을 받아 data/ 에 저장한다.

build.py 가 실행될 때마다 먼저 호출된다. 네트워크가 막히거나 상대 사이트 구조가 바뀌어
실패하면 이전에 저장해 둔 data/ 파일을 그대로 쓰므로 홈페이지 빌드는 멈추지 않는다.
"""
import html
import io
import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

SRC = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(SRC, "data")
BLOG_ID = "behalf1oj"
INSTA_USER = "gangsan_30"
BLOG_IMG_DIR = os.path.join(DATA, "blog_img")
INSTA_IMG_DIR = os.path.join(DATA, "insta_img")
UA_MOBILE = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148"


def get(url, headers=None, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA_MOBILE, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def save_image(url, path, max_side=1000):
    if os.path.exists(path):
        return True
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(get(url, {"Referer": "https://m.blog.naver.com/"}))).convert("RGB")
        im.thumbnail((max_side, max_side), Image.LANCZOS)
        im.save(path, quality=82, optimize=True, progressive=True)
        return True
    except Exception as e:  # 이미지 하나 실패는 건너뛴다
        print("  image skip:", url[:80], e, file=sys.stderr)
        return False


def strip(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s)).replace("​", "").strip()


def parse_post(raw, log_no):
    """본문을 [{"t": "p"|"h"|"img"|"table", ...}] 블록 목록으로 바꾼다."""
    body = raw[raw.find("se-main-container"):]
    parts = re.split(r'<div class="se-component (se-[a-zA-Z]+)', body)
    blocks, n_img = [], 0
    for kind, chunk in zip(parts[1::2], parts[2::2]):
        if kind == "se-text":
            for p in re.findall(r'<p class="se-text-paragraph[^>]*>(.*?)</p>', chunk, re.S):
                t = strip(p)
                if t:
                    blocks.append({"t": "p", "text": t})
        elif kind == "se-quotation":
            t = " ".join(strip(p) for p in re.findall(r'<p class="se-text-paragraph[^>]*>(.*?)</p>', chunk, re.S)).strip()
            if t:
                blocks.append({"t": "h" if len(t) <= 40 else "quote", "text": t})
        elif kind in ("se-image", "se-imageGroup", "se-imageStrip"):
            for u in dict.fromkeys(re.findall(r'(?:data-lazy-src|src)="(https://(?:mblogthumb-phinf|postfiles)\.pstatic\.net/[^"?]+)', chunk)):
                n_img += 1
                name = f"{log_no}-{n_img}.jpg"
                if save_image(u + "?type=w966", os.path.join(BLOG_IMG_DIR, name)):
                    cap = re.search(r'se-image-caption.*?<p[^>]*>(.*?)</p>', chunk, re.S)
                    blocks.append({"t": "img", "src": name, "alt": strip(cap.group(1)) if cap else ""})
        elif kind == "se-table":
            rows = []
            for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", chunk, re.S):
                cells = [strip(td) for td in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
                if any(cells):
                    rows.append(cells)
            if rows:
                blocks.append({"t": "table", "rows": rows})
    return blocks


def sync_blog():
    os.makedirs(BLOG_IMG_DIR, exist_ok=True)
    path = os.path.join(DATA, "blog.json")
    old = {}
    if os.path.exists(path):
        old = {p["id"]: p for p in json.load(open(path, encoding="utf-8"))}
    try:
        root = ET.fromstring(get(f"https://rss.blog.naver.com/{BLOG_ID}.xml")).find("channel")
    except Exception as e:
        print("blog: RSS 실패, 저장본 사용:", e, file=sys.stderr)
        return
    posts = []
    for it in root.findall("item"):
        log_no = re.search(r"/(\d+)", it.findtext("link")).group(1)
        if log_no in old and old[log_no].get("blocks"):
            posts.append(old[log_no])
            continue
        date = datetime.strptime(it.findtext("pubDate"), "%a, %d %b %Y %H:%M:%S %z")
        post = {
            "id": log_no,
            "title": strip(it.findtext("title")),
            "date": date.strftime("%Y-%m-%d"),
            "url": f"https://blog.naver.com/{BLOG_ID}/{log_no}",
            "summary": strip(it.findtext("description"))[:180],
            "tags": [t.strip() for t in (it.findtext("tag") or "").split(",") if t.strip()],
            "blocks": [],
        }
        try:
            post["blocks"] = parse_post(get(f"https://m.blog.naver.com/{BLOG_ID}/{log_no}").decode("utf-8", "replace"), log_no)
        except Exception as e:
            print("blog: 본문 실패", log_no, e, file=sys.stderr)
        posts.append(post)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=1)
    print(f"blog: {len(posts)}개 글")


def fetch_instagram_official(token):
    """Instagram API(인스타그램 로그인 방식). GitHub 저장소 Secret IG_TOKEN 에 장기 토큰을 넣으면 사용된다."""
    try:  # 토큰 유효기간(60일)을 실행할 때마다 연장한다. 실패해도 기존 토큰으로 계속 진행
        get(f"https://graph.instagram.com/refresh_access_token?grant_type=ig_refresh_token&access_token={token}")
    except Exception:
        pass
    fields = "id,caption,media_type,media_url,thumbnail_url,permalink,timestamp"
    data = json.loads(get(f"https://graph.instagram.com/me/media?fields={fields}&limit=24&access_token={token}"))["data"]
    items = []
    for m in data:
        code = m["permalink"].rstrip("/").split("/")[-1]
        thumb = m.get("thumbnail_url") or m.get("media_url")
        if not thumb or not save_image(thumb, os.path.join(INSTA_IMG_DIR, f"{code}.jpg"), 720):
            continue
        items.append({
            "code": code,
            "url": m["permalink"] if m["permalink"].endswith("/") else m["permalink"] + "/",
            "video": m["media_type"] == "VIDEO",
            "date": m["timestamp"][:10],
            "caption": (m.get("caption") or "").replace("\u200b", "").strip(),
        })
    return items


def sync_instagram():
    os.makedirs(INSTA_IMG_DIR, exist_ok=True)
    path = os.path.join(DATA, "instagram.json")
    token = os.environ.get("IG_TOKEN", "").strip()
    if token:
        try:
            items = fetch_instagram_official(token)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False, indent=1)
            print(f"instagram(공식 API): {len(items)}개 게시물")
            return
        except Exception as e:
            print("instagram 공식 API 실패, 공개 프로필로 시도:", str(e).split("access_token")[0], file=sys.stderr)
    try:
        raw = get(f"https://i.instagram.com/api/v1/users/web_profile_info/?username={INSTA_USER}",
                  {"x-ig-app-id": "936619743392459", "User-Agent": UA_MOBILE + " Instagram 300.0"})
        edges = json.loads(raw)["data"]["user"]["edge_owner_to_timeline_media"]["edges"]
    except Exception as e:
        print("instagram: 실패, 저장본 사용:", e, file=sys.stderr)
        return
    items = []
    for e in edges:
        n = e["node"]
        cap = (n["edge_media_to_caption"]["edges"] or [{"node": {"text": ""}}])[0]["node"]["text"]
        code = n["shortcode"]
        is_reel = n.get("product_type") == "clips"
        if not save_image(n["display_url"], os.path.join(INSTA_IMG_DIR, f"{code}.jpg"), 720):
            continue
        items.append({
            "code": code,
            "url": f"https://www.instagram.com/{'reel' if is_reel else 'p'}/{code}/",
            "video": bool(n.get("is_video")),
            "date": datetime.fromtimestamp(n["taken_at_timestamp"]).strftime("%Y-%m-%d"),
            "caption": cap.replace("​", "").strip(),
        })
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=1)
    print(f"instagram: {len(items)}개 게시물")


if __name__ == "__main__":
    os.makedirs(DATA, exist_ok=True)
    sync_blog()
    sync_instagram()
