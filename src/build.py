# -*- coding: utf-8 -*-
"""강산자원 정적 홈페이지 생성기.

사용법:  python3 build.py            (블로그·인스타 최신 글을 받아온 뒤 생성)
         python3 build.py --offline  (저장된 data/ 만으로 생성)
결과물:  ../dist  (웹호스팅에 그대로 올리면 되는 파일들)
"""
import html
import json
import os
import re
import shutil
import sys
from datetime import date

from PIL import Image, ImageDraw, ImageFont, ImageOps

import columns as CL
import content as C
import content_more as M

SRC = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(os.path.dirname(SRC), "dist")
DATA = os.path.join(SRC, "data")
TODAY = date.today().isoformat()
RFC_DATE = date.today().strftime("%a, %d %b %Y 00:00:00 +0900")
B = C.BIZ
e = html.escape

# ---------------------------------------------------------------- 데이터 정리
SERVICES = list(C.SERVICES)
SERVICES.insert(4, M.TRASH_SERVICE)  # 유품정리 다음에 쓰레기집
for s in SERVICES:
    s.update({k: v for k, v in M.SERVICE_MORE.get(s["slug"], {}).items() if k in ("self", "approach")})
    s["more_faqs"] = M.SERVICE_MORE.get(s["slug"], {}).get("faqs", [])
SVC = {s["slug"]: s for s in SERVICES}
SVC_SUB = {
    "household": "장롱·침대·소파 등 큰 가구 방문 수거", "appliances": "냉장고·에어컨·세탁기·업소용 가전",
    "moving": "이사 전후 남은 짐 한 번에", "estate": "부모님 댁·고인의 집 정리",
    "trash-house": "쓰레기와 짐이 쌓인 집 비우기", "office": "책상·파티션·캐비닛 철수",
    "store": "폐업 매장 철거부터 원상복구까지", "demolition": "욕실·주방·가벽·바닥재 철거",
    "business": "폐목재·파렛트·판넬·공사 잔재", "small": "가구 2~3개도 출동",
    "outdoor": "화분·옥상·베란다·창고 정리",
}


def has_img(cid):
    return os.path.exists(os.path.join(SRC, "images", "cases", f"{cid}-before.jpg")) and \
        os.path.exists(os.path.join(SRC, "images", "cases", f"{cid}-after.jpg"))


CASES = [dict(id=i, title=t, cat=c, service=s, desc=d) for i, t, c, s, d in M.CASES if has_img(i)]
CASE = {c["id"]: c for c in CASES}
CATS = [(k, n, d) for k, n, d in M.CASE_CATS if any(c["cat"] == k for c in CASES)]
CAT_NAME = {k: n for k, n, _ in CATS}
ITEMS = M.ITEMS
GUIDES = list(C.GUIDES) + [M.TRASH_GUIDE]


def cases_for_service(slug, n=3):
    own = [CASE[i] for i in SVC[slug].get("cases", []) if i in CASE]
    auto = [c for c in CASES if c["service"] == slug and c not in own]
    return (own + auto)[:n]


def load_json(name):
    p = os.path.join(DATA, name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else []


BLOG = []
INSTA = []
PAGES = []  # (path, title, desc, images, indexable)


def url(path):
    return C.SITE_URL.rstrip("/") + "/" + ("" if path == "index.html" else path)


def rel(from_path, to_path):
    return "../" * from_path.count("/") + to_path


# ---------------------------------------------------------------- 공유 썸네일(OG) 이미지
FONT_D = os.path.join(SRC, "fonts", "BlackHanSans-Regular.ttf")
FONT_B = os.path.join(SRC, "fonts", "IBMPlexSansKR-Bold.ttf")


def wrap_px(draw, text, font, width):
    lines, cur = [], ""
    for word in text.split(" "):
        test = (cur + " " + word).strip()
        if draw.textlength(test, font=font) <= width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            while draw.textlength(word, font=font) > width:  # 아주 긴 단어는 글자 단위로 자른다
                k = len(word)
                while draw.textlength(word[:k], font=font) > width:
                    k -= 1
                lines.append(word[:k]); word = word[k:]
            cur = word
    if cur:
        lines.append(cur)
    return lines


PAIR_RE = re.compile(r"images/cases/([A-Za-z0-9]+)-(?:before|after)\.jpg$")


def case_pair(photo):
    """사례 사진 경로면 (작업 전, 작업 후) 경로 쌍을 돌려준다."""
    m = PAIR_RE.search(photo or "")
    if not m:
        return None
    return case_photo(m.group(1), "before"), case_photo(m.group(1), "after")


def paste_pair(im, pair, box):
    """box 영역에 작업 전·후 사진을 나란히 붙이고 라벨을 단다."""
    x0, y0, x1, y1 = box
    half = (x1 - x0) // 2
    d = ImageDraw.Draw(im)
    fl = ImageFont.truetype(FONT_B, max(18, (y1 - y0) // 26))
    for i, (src, label) in enumerate(zip(pair, ("작업 전", "작업 후"))):
        ph = ImageOps.fit(Image.open(src).convert("RGB"), (half, y1 - y0), Image.LANCZOS)
        im.paste(ph, (x0 + i * half, y0))
        tw = d.textlength(label, font=fl)
        bx, by = x0 + i * half + 16, y0 + 16
        d.rounded_rectangle((bx, by, bx + tw + 24, by + fl.size + 16), radius=8, fill="#f6c945" if i else "#15211b")
        d.text((bx + 12, by + 6), label, font=fl, fill="#1b1600" if i else "#ffffff")
    d.rectangle((x0 + half - 3, y0, x0 + half + 3, y1), fill="#f6c945")


def make_og(key, title, sub, photo):
    """1200x630 공유 이미지. 사례 사진이면 작업 전·후를 나란히 넣는다. 네이버·카카오·구글 썸네일에 쓰인다."""
    out_rel = f"images/og/{key}.jpg"
    out = os.path.join(DIST, out_rel)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    pair = case_pair(photo)
    W, H = 1200, 630
    PW = 660 if pair else 520
    im = Image.new("RGB", (W, H), "#1c5a3e")
    if pair:
        paste_pair(im, pair, (W - PW, 0, W, H))
    elif photo and os.path.exists(photo):
        im.paste(ImageOps.fit(Image.open(photo).convert("RGB"), (PW, H), Image.LANCZOS), (W - PW, 0))
    d = ImageDraw.Draw(im)
    x, maxw = 56, W - PW - 56 - 36
    d.text((x, 52), "강산자원", font=ImageFont.truetype(FONT_D, 38), fill="#f6c945")
    title = title.replace("·", ", ")  # 제목 글꼴에 가운뎃점이 없다
    size = 60
    while True:
        ft = ImageFont.truetype(FONT_D, size)
        lines = [ln for part in title.split("\n") for ln in wrap_px(d, part, ft, maxw)]
        if len(lines) <= 3 or size <= 40:
            break
        size -= 4
    y = 132
    for ln in lines[:3]:
        d.text((x, y), ln, font=ft, fill="#ffffff"); y += int(size * 1.22)
    fs = ImageFont.truetype(FONT_B, 24)
    y += 12
    for ln in wrap_px(d, sub, fs, maxw)[:3]:
        d.text((x, y), ln, font=fs, fill="#d9eadf"); y += 36
    d.text((x, H - 128), "30년 경력 · 사진 무료 견적", font=ImageFont.truetype(FONT_B, 22), fill="#cfe3d8")
    d.rounded_rectangle((x, H - 92, x + 320, H - 40), radius=26, fill="#f6c945")
    d.text((x + 160, H - 66), "전화 010-6338-4016", font=ImageFont.truetype(FONT_B, 26), fill="#1b1600", anchor="mm")
    im.save(out, quality=86, optimize=True, progressive=True)
    return out_rel


def make_thumb(key, title, photo):
    """정사각형 전후 썸네일(1000x1000). 검색 결과의 사진 카드용으로 본문 첫 사진과 og:image에 함께 쓴다."""
    pair = case_pair(photo)
    if not pair:
        return None
    out_rel = f"images/thumb/{key}.jpg"
    out = os.path.join(DIST, out_rel)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    S, band = 1000, 150
    im = Image.new("RGB", (S, S), "#1c5a3e")
    paste_pair(im, pair, (0, 0, S, S - band))
    d = ImageDraw.Draw(im)
    t = title.replace("·", ", ")
    size = 52
    ft = ImageFont.truetype(FONT_D, size)
    while d.textlength(t, font=ft) > S - 80 and size > 30:
        size -= 4; ft = ImageFont.truetype(FONT_D, size)
    d.text((40, S - band + 26), t, font=ft, fill="#ffffff")
    d.text((40, S - 52), "강산자원 · 30년 경력 · 010-6338-4016", font=ImageFont.truetype(FONT_B, 26), fill="#f6c945")
    im.save(out, quality=86, optimize=True, progressive=True)
    return out_rel


def case_photo(cid, side="after"):
    return os.path.join(SRC, "images", "cases", f"{cid}-{side}.jpg")


DEFAULT_PHOTO = case_photo("b275")

# ---------------------------------------------------------------- 공통 조각
ICON_PHONE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2"/></svg>'
ICON_CHAT = '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 3C6.5 3 2 6.6 2 11c0 2.8 1.8 5.3 4.6 6.7l-1 3.6c-.1.4.3.7.6.5l4.2-2.8c.5.1 1.1.1 1.6.1 5.5 0 10-3.6 10-8.1S17.5 3 12 3z"/></svg>'
ICON_PLAY = '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>'


def btn_call(label=None):
    return f'<a class="btn btn-call" href="tel:{B["phone"].replace("-", "")}">{ICON_PHONE}<span>{e(label or B["phone"])}</span></a>'


def btn_kakao(label="카톡으로 사진 견적"):
    return f'<a class="btn btn-kakao" href="{B["kakao_chat"]}" target="_blank" rel="noopener">{ICON_CHAT}<span>{e(label)}</span></a>'


def menu_groups():
    """메가메뉴 구성: (제목, 대표 링크, [(링크, 이름, 설명)], 촘촘하게 여부)"""
    col = [(f"column/{t['slug']}.html", t["title"], "") for t in CL.TOPIC.values()]
    loc = [(f"local/{r['slug']}.html", r["name"], "") for r in CL.REGION.values()]
    return [
        ("서비스", "services/index.html", [(f"services/{s['slug']}.html", s["name"], SVC_SUB[s["slug"]]) for s in SERVICES], False),
        ("품목별 수거", "items/index.html", [(f"items/{i['slug']}.html", i["name"], i["sub"]) for i in ITEMS], False),
        ("작업사례", "cases/index.html", [("cases/index.html", "전체 사례", f"전후 사진 {len(CASES)}건")] +
         [(f"cases/{k}.html", n, f"{sum(1 for c in CASES if c['cat'] == k)}건") for k, n, _ in CATS], False),
        ("폐기물 칼럼", "column/index.html", col, True),
        ("지역별 안내", "local/index.html", loc, True),
        ("소식", "daily/index.html", [("daily/index.html", "강산 일상", "블로그 현장 이야기"), ("videos.html", "현장 영상", "인스타그램 릴스")], False),
        ("이용안내", "estimate.html", [("estimate.html", "무료견적·작업 절차", "사진으로 받는 무료 견적"), ("areas/index.html", "출동지역", "서울·경기·인천 전 지역"),
                                    ("guide/index.html", "폐기물 처리 가이드", f"현장 경험으로 쓴 안내 {len(GUIDES)}편"), ("faq.html", "자주 묻는 질문", "견적·일정·작업 범위"),
                                    ("reviews.html", "고객 후기", "당근·플레이스 후기")], False),
        ("회사소개", "about.html", [("about.html", "강산자원 소개", "30년 경력, 대표 직접 출동"), ("about.html#vehicles", "보유 차량", "1톤 트럭·집게차·사다리차"),
                                 ("contact.html", "연락처·오시는 길", "은평구 증산동 본사")], False),
    ]


def fit(text, limit):
    """네이버 권장 길이(제목 40자, 설명 80자)에 맞춘다. 문장·쉼표 단위로 자르고, 안 되면 단어 단위."""
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    for sep in (". ", ", ", " · ", " "):
        i = cut.rfind(sep)
        if i >= limit * 0.6:
            return cut[:i].rstrip(" ,·") + ("." if sep == ". " else "")
    return cut.rstrip()


def page(path, title, desc, main, head_html="", crumbs=None, ld=None, head_title=None,
         og_photo=None, og_sub=None, indexable=True, canonical=None, images=None):
    full_title = fit(head_title or f"{title} | 강산자원", 40)
    if not full_title.endswith("강산자원") and not full_title.startswith("강산자원"):
        full_title = fit(title, 40 - len(" | 강산자원")) + " | 강산자원"
    desc = fit(desc, 80)
    og_key = "home" if path == "index.html" else re.sub(r"[^a-z0-9]+", "-", path.replace(".html", "").lower()).strip("-")
    og_rel = make_og(og_key, title if path != "index.html" else "버리기 힘든 짐,\n한 번에 비워드립니다",
                     og_sub or desc[:70], og_photo or DEFAULT_PHOTO)
    thumb_rel = None
    if path.startswith(("services/", "items/", "cases/", "guide/", "column/", "local/")) and not path.endswith("index.html") or path == "index.html":
        thumb_rel = make_thumb(og_key, title if path != "index.html" else "버리기 힘든 짐, 한 번에", og_photo or DEFAULT_PHOTO)
    if thumb_rel and '<article class="prose">' in main and path != "index.html" and "pair-gallery" not in main:
        fig = (f'<figure class="lead-thumb"><img src="{rel(path, thumb_rel)}" alt="{e(title)} 작업 전후 사진 - 강산자원" width="1000" height="1000" decoding="async">'
               f'<figcaption>{e(title)} 실제 작업 전과 후</figcaption></figure>')
        main = main.replace('<article class="prose">', '<article class="prose">' + fig, 1)
    PAGES.append((path, title, desc, [og_rel] + ([thumb_rel] if thumb_rel else []) + (images or []), indexable))
    crumbs = crumbs or []
    graph = [business_ld(), {
        "@type": "WebPage", "@id": url(path), "url": url(path), "name": full_title,
        "description": desc, "inLanguage": "ko-KR", "dateModified": TODAY,
        "primaryImageOfPage": {"@type": "ImageObject", "url": url(og_rel), "width": 1200, "height": 630},
        "image": [url(og_rel)] + ([url(thumb_rel)] if thumb_rel else []),
        "isPartOf": {"@type": "WebSite", "name": "강산자원", "url": url("index.html")},
        "about": {"@id": url("index.html") + "#business"},
    }]
    if crumbs:
        graph.append(crumbs_ld([("index.html", "홈")] + crumbs))
    graph += ld or []
    ld_json = json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    r = lambda p: rel(path, p)
    top = path.split("/")[0] if "/" in path else path

    nav_items = []
    for gname, glink, links, compact in menu_groups():
        cur = ' aria-current="page"' if (glink.split("/")[0] == top or any(l.split("#")[0] == path for l, _, _ in links)) else ""
        if links:
            panel = "".join(f'<a href="{r(l)}"><b>{e(n)}</b>' + (f'<span>{e(s)}</span>' if s else "") + "</a>" for l, n, s in links)
            nav_items.append(f'<li class="has-mega"><a href="{r(glink)}"{cur}>{e(gname)}</a><div class="mega"><div class="mega-inner"><p class="mega-title">{e(gname)}</p><div class="mega-grid{" compact" if compact else ""}">{panel}</div></div></div></li>')
        else:
            nav_items.append(f'<li><a href="{r(glink)}"{cur}>{e(gname)}</a></li>')
    mob = [f'<a href="{r("index.html")}">홈</a>']
    for gname, glink, links, _ in menu_groups():
        if links:
            mob.append(f'<details><summary>{e(gname)}</summary><div>' + "".join(f'<a href="{r(l)}">{e(n)}</a>' for l, n, _ in links) + "</div></details>")
        else:
            mob.append(f'<a href="{r(glink)}">{e(gname)}</a>')

    crumb_html = ""
    if crumbs:
        items = [f'<li><a href="{r("index.html")}">홈</a></li>'] + [
            (f'<li><a href="{r(p)}">{e(n)}</a></li>' if i < len(crumbs) - 1 else f'<li aria-current="page">{e(n)}</li>')
            for i, (p, n) in enumerate(crumbs)]
        crumb_html = f'<nav aria-label="현재 위치"><ol class="crumbs">{"".join(items)}</ol></nav>'
    page_head = f'<div class="page-head"><div class="wrap">{crumb_html}{head_html}</div></div>' if head_html else ""
    svc_links = "".join(f'<li><a href="{r("services/" + s["slug"] + ".html")}">{e(s["name"])}</a></li>' for s in SERVICES)
    robots = "index,follow,max-image-preview:large" if indexable else "noindex,follow"
    doc = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{e(full_title)}</title>
<meta name="claude:viewport-fit-sides" content="cover">
<meta name="description" content="{e(desc)}">
<meta name="robots" content="{robots}">
<link rel="canonical" href="{canonical or url(path)}">
<meta property="og:type" content="{'article' if path.startswith(('guide/', 'daily/')) and not path.endswith('index.html') else 'website'}">
<meta property="og:site_name" content="강산자원">
<meta property="og:locale" content="ko_KR">
<meta property="og:title" content="{e(full_title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{url(path)}">
<meta property="og:image" content="{url(og_rel)}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{e(title)} 작업 전후 - 강산자원">
{f'<meta property="og:image" content="{url(thumb_rel)}"><meta property="og:image:width" content="1000"><meta property="og:image:height" content="1000">' if thumb_rel else ''}
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{url(og_rel)}">
<meta name="thumbnail" content="{url(og_rel)}">
<meta name="theme-color" content="#1c5a3e">
<meta name="format-detection" content="telephone=no">
<!-- 네이버 서치어드바이저 / 구글 서치콘솔 소유확인 코드를 받으면 content.py 의 VERIFY 값에 넣으세요 -->
{''.join(f'<meta name="{k}" content="{v}">' for k, v in getattr(C, 'VERIFY', {}).items() if v)}
<link rel="icon" href="{r("favicon.svg")}" type="image/svg+xml">
<link rel="apple-touch-icon" href="{r("images/logo.png")}">
<link rel="alternate" type="text/plain" title="LLM summary" href="{r("llms.txt")}">
<link rel="alternate" type="application/rss+xml" title="강산자원" href="{r("rss.xml")}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Black+Han+Sans&family=IBM+Plex+Sans+KR:wght@400;600;700&display=swap">
<link rel="stylesheet" href="{r("assets/site.css")}">
<script type="application/ld+json">{ld_json}</script>
{analytics_html()}
</head>
<body>
<a class="skip" href="#main">본문 바로가기</a>
<header class="site-header">
  <div class="wrap">
    <a class="logo" href="{r("index.html")}" aria-label="강산자원 홈"><b>강산자원</b><span>폐기물 처리 30년</span></a>
    <nav class="nav" aria-label="주 메뉴"><ul>{"".join(nav_items)}</ul></nav>
    <div class="header-call">{btn_call()}</div>
    <details class="menu"><summary>메뉴</summary><nav class="menu-panel" aria-label="모바일 메뉴">{"".join(mob)}</nav></details>
  </div>
</header>
<main id="main">
{page_head}{main}
<section class="closing" aria-labelledby="closing-title">
  <div class="wrap">
    <div>
      <h2 id="closing-title">사진 몇 장이면 견적이 나옵니다</h2>
      <p>버릴 물건과 현장 사진을 카카오톡으로 보내주세요. 24시간 상담, 견적은 무료입니다.</p>
    </div>
    <div class="btn-row">{btn_kakao()}{btn_call()}</div>
  </div>
</section>
</main>
<footer class="site-footer">
  <div class="wrap">
    <div>
      <h2>강산자원</h2>
      <p>30년 경력 폐기물 처리·실내철거 전문<br>{e(B["address"])} (증산동 186-6)<br>대표전화 <span class="tel">{B["phone"]}</span><br>24시간 상담 · 연중무휴 · 100% 예약제</p>
    </div>
    <div>
      <h2>서비스</h2>
      <ul>{svc_links}</ul>
    </div>
    <div>
      <h2>안내</h2>
      <ul>
        <li><a href="{r("items/index.html")}">품목별 수거</a></li>
        <li><a href="{r("cases/index.html")}">작업사례 (전후 사진)</a></li>
        <li><a href="{r("daily/index.html")}">강산 일상 (현장 이야기)</a></li>
        <li><a href="{r("videos.html")}">작업 영상</a></li>
        <li><a href="{r("estimate.html")}">무료견적·작업 절차</a></li>
        <li><a href="{r("guide/index.html")}">폐기물 처리 가이드</a></li>
        <li><a href="{r("faq.html")}">자주 묻는 질문</a></li>
        <li><a href="{r("reviews.html")}">고객 후기</a></li>
        <li><a href="{r("areas/index.html")}">출동지역</a></li>
        <li><a href="{r("contact.html")}">연락처·오시는 길</a></li>
      </ul>
    </div>
    <div>
      <h2>채널</h2>
      <ul>
        <li><a href="{B["kakao_channel"]}" target="_blank" rel="noopener">카카오톡 채널</a></li>
        <li><a href="{B["naver_place"]}" target="_blank" rel="noopener">네이버 플레이스</a></li>
        <li><a href="https://blog.naver.com/{BLOG_ID}" target="_blank" rel="noopener">네이버 블로그</a></li>
        <li><a href="{B["instagram"]}" target="_blank" rel="noopener">인스타그램</a></li>
        <li><a href="{B["daangn"]}" target="_blank" rel="noopener">당근 동네업체</a></li>
      </ul>
      <p style="margin-top:12px">© 강산자원</p>
    </div>
  </div>
</footer>
<div class="actionbar">{btn_call("전화하기")}{btn_kakao("카톡 사진견적")}</div>
<script src="{r("assets/site.js")}" defer></script>
</body>
</html>
"""
    out = os.path.join(DIST, path)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(doc)


BLOG_ID = "behalf1oj"


def analytics_html():
    a = getattr(C, "ANALYTICS", {})
    out = ""
    if a.get("ga4"):
        g = e(a["ga4"])
        out += (f'<script async src="https://www.googletagmanager.com/gtag/js?id={g}"></script>'
                f"<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','{g}');</script>")
    if a.get("naver"):
        out += ('<script src="https://wcs.naver.net/wcslog.js"></script>'
                f'<script>if(!window.wcs_add)window.wcs_add={{}};wcs_add["wa"]="{e(a["naver"])}";if(window.wcs){{wcs_do();}}</script>')
    return out


def business_ld():
    return {
        "@type": "LocalBusiness", "@id": url("index.html") + "#business",
        "name": B["name"], "alternateName": B["name_en"],
        "description": "서울 은평구 증산동에 본사를 둔 30년 경력 폐기물 처리·실내철거 전문업체. 대형폐기물·폐가구·폐가전 수거, 이사 폐기물, 유품정리, 쓰레기집 정리·청소, 사무실·상가 원상복구, 실내철거. 서울·경기·인천 수도권 전 지역 출동, 사진 무료 견적.",
        "url": url("index.html"), "telephone": B["phone_intl"],
        "image": url("images/og/home.jpg"), "logo": url("images/logo.png"),
        "priceRange": "사진 무료 견적",
        "address": {"@type": "PostalAddress", "streetAddress": B["address_parts"]["street"], "addressLocality": B["address_parts"]["locality"],
                    "addressRegion": B["address_parts"]["region"], "addressCountry": "KR"},
        "openingHoursSpecification": [{"@type": "OpeningHoursSpecification", "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"], "opens": "00:00", "closes": "23:59"}],
        "areaServed": [{"@type": "AdministrativeArea", "name": n} for n in ("서울특별시", "경기도", "인천광역시")],
        "knowsAbout": ["대형폐기물 수거", "폐가구 수거", "폐가전 수거", "이사 폐기물", "유품정리", "쓰레기집 정리", "쓰레기집 청소", "사무실 폐기물", "상가 원상복구", "실내철거", "사업장 폐기물"],
        "hasOfferCatalog": {"@type": "OfferCatalog", "name": "강산자원 서비스",
                            "itemListElement": [{"@type": "Offer", "itemOffered": {"@type": "Service", "name": s["name"], "url": url(f"services/{s['slug']}.html")}} for s in SERVICES]},
        "sameAs": [B["naver_place"], B["daangn"], B["instagram"], B["kakao_channel"], f"https://blog.naver.com/{BLOG_ID}"],
    }


def crumbs_ld(crumbs):
    return {"@type": "BreadcrumbList", "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": n, "item": url(p)} for i, (p, n) in enumerate(crumbs)]}


def faq_ld(faqs):
    return {"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faqs]}


def head(title, lead, eyebrow=""):
    return (f'<span class="eyebrow">{e(eyebrow)}</span>' if eyebrow else "") + f'<h1>{e(title)}</h1><p>{e(lead)}</p>'


def img(path_from, src, alt, w=900, h=1200, lazy=True, cls=""):
    attrs = f' class="{cls}"' if cls else ""
    attrs += ' loading="lazy"' if lazy else ""
    return f'<img{attrs} src="{rel(path_from, src)}" alt="{e(alt)}" width="{w}" height="{h}" decoding="async">'


def case_card(path, c, lazy=True):
    s = SVC[c["service"]]
    return f"""<article class="case" data-tag="{e(c['cat'])}">
  <div class="case-pair">
    <figure>{img(path, f"images/cases/{c['id']}-before.jpg", c['title'] + ' 작업 전 모습', lazy=lazy)}<figcaption>작업 전</figcaption></figure>
    <figure>{img(path, f"images/cases/{c['id']}-after.jpg", c['title'] + ' 작업 후 모습', lazy=lazy)}<figcaption>작업 후</figcaption></figure>
  </div>
  <span class="tag"><a href="{rel(path, 'cases/' + c['cat'] + '.html')}">{e(CAT_NAME[c['cat']])}</a>{'' if CAT_NAME[c['cat']] == s['name'] else f""" · <a href="{rel(path, 'services/' + s['slug'] + '.html')}">{e(s['name'])}</a>"""}</span>
  <h3>{e(c['title'])}</h3>
  <p>{e(c['desc'])}</p>
</article>"""


def case_imgs(cs):
    return [f"images/cases/{c['id']}-{side}.jpg" for c in cs for side in ("before", "after")]


def faq_html(faqs, open_first=False):
    return '<div class="faq">' + "".join(
        f'<details{" open" if open_first and i == 0 else ""}><summary>{e(q)}</summary><div class="a"><p>{e(a)}</p></div></details>'
        for i, (q, a) in enumerate(faqs)) + "</div>"


def sheet(rows, title="강산자원 한눈에 보기", sub="작업 안내서"):
    dl = "".join(f"<dt>{e(k)}</dt><dd>{e(v)}</dd>" for k, v in rows)
    return f'<div class="sheet"><div class="sheet-title"><b>{e(title)}</b><span>{e(sub)}</span></div><dl>{dl}</dl></div>'


def cta_card():
    return f"""<div class="cta-card">
  <b>사진 보내고 무료 견적</b>
  <p>카카오톡으로 현장 사진, 주소(동까지), 층수, 엘리베이터 유무를 보내주세요.</p>
  {btn_kakao()}
  {btn_call()}
  <p class="tel">24시간 상담 · 연중무휴</p>
</div>"""


def steps_html(steps, cls="steps"):
    return f'<ol class="{cls}">' + "".join(f"<li><h3>{e(t)}</h3><p>{e(d)}</p></li>" for t, d in steps) + "</ol>"


def link_cards(path, links):
    return '<div class="link-list">' + "".join(f'<a href="{rel(path, l)}"><b>{e(n)}</b><span>{e(d)}</span></a>' for l, n, d in links) + "</div>"


def insta_card(path, v, lazy=True):
    cap_lines = [ln.strip() for ln in v["caption"].splitlines() if ln.strip() and not ln.strip().startswith("#")]
    title = re.sub(r"^제목\s*:\s*", "", cap_lines[0] if cap_lines else "강산자원 작업 영상")
    body = " ".join(cap_lines[1:])[:150]
    kind = "릴스" if v["video"] else "사진"
    return f"""<article class="video">
  <a class="video-thumb" href="{v['url']}" target="_blank" rel="noopener" data-embed="{v['url']}embed/">
    {img(path, f"images/insta/{v['code']}.jpg", title, 720, 900, lazy=lazy)}
    <span class="video-play">{ICON_PLAY if v['video'] else ''}<em>{kind} 보기</em></span>
  </a>
  <h3>{e(title)}</h3>
  <p>{e(body)}</p>
  <span class="tag">{v['date']} · <a href="{v['url']}" target="_blank" rel="noopener">인스타그램에서 보기</a></span>
</article>"""


def blog_thumb(p):
    for b in p["blocks"]:
        if b["t"] == "img":
            return f"images/daily/{b['src']}"
    return None


def blog_card(path, p):
    th = blog_thumb(p)
    return f"""<a class="post" href="{rel(path, 'daily/' + p['id'] + '.html')}">
  {img(path, th, p['title'], 900, 900) if th else ''}
  <span class="tag">{p['date']}</span>
  <h3>{e(p['title'])}</h3>
  <p>{e(p['summary'][:110])}</p>
</a>"""


# ---------------------------------------------------------------- 홈
def build_home():
    p = "index.html"
    hero = CASE["b275"]
    svc_items = "".join(
        f'<a class="svc" href="services/{s["slug"]}.html"><h3><small>{i + 1:02d}</small>{e(s["name"])}</h3><p>{e(s["short"])}</p><span class="more">자세히 보기 →</span></a>'
        for i, s in enumerate(SERVICES))
    home_cases = [CASE[i] for i in ["g000", "g012", "g090", "g109", "g131", "g047"] if i in CASE]
    cases = "".join(case_card(p, c) for c in home_cases)
    why = "".join(f"<div><h3>{e(t)}</h3><p>{e(d)}</p></div>" for t, d in C.WHY)
    reviews = "".join(f'<blockquote class="review"><p>{e(t)}</p><footer>당근 동네업체 후기 · {e(k)}</footer></blockquote>' for k, t in C.REVIEWS[:3])
    vehicles = "".join(f'<div class="vehicle"><b>{e(v["name"])}</b><p><strong>주요 작업</strong> {e(v["use"])}</p><p>{e(v["note"])}</p></div>' for v in C.VEHICLES)
    area_rows = "".join(f'<tr><th scope="row"><a href="areas/{k}.html">{e(a["full"])}</a></th><td>{e(", ".join(a["districts"]))}</td></tr>' for k, a in C.AREAS.items())
    item_chips = "".join(f'<li><a href="items/{i["slug"]}.html">{e(i["name"])}</a></li>' for i in ITEMS)
    videos = "".join(insta_card(p, v) for v in INSTA[:4])
    posts = "".join(blog_card(p, x) for x in BLOG[:3])
    main = f"""
<section class="hero">
  <div class="wrap">
    <div class="hero-copy">
      <span class="eyebrow">서울·경기·인천 폐기물 처리 · 쓰레기집 정리 · 실내철거</span>
      <h1>버리기 힘든 짐,<br><em>30년 경력</em> 강산자원이<br>한 번에 비워드립니다</h1>
      <p class="hero-lead">가구 한 개부터 쓰레기집, 건물 한 동까지. 대표가 직접 출동하고, 본사 직원이 분해·운반·반출을 모두 맡습니다. 사진만 보내시면 견적은 무료입니다.</p>
      <ul class="hero-tags"><li>10,000곳 이상 출동</li><li>100% 예약제</li><li>주말·공휴일 작업</li><li>수도권 당일 출동</li></ul>
      <div class="btn-row">{btn_kakao()}{btn_call()}</div>
    </div>
    <div>
      <div class="ba" style="--pos:50%">
        {img(p, f"images/cases/{hero['id']}-after.jpg", hero['title'] + ' 작업 후', lazy=False)}
        {img(p, f"images/cases/{hero['id']}-before.jpg", hero['title'] + ' 작업 전', lazy=False, cls="ba-before")}
        <span class="ba-handle"></span>
        <span class="ba-label l">작업 전</span><span class="ba-label r">작업 후</span>
        <input type="range" min="0" max="100" value="50" aria-label="작업 전후 비교 슬라이더">
      </div>
      <p class="ba-caption">실제 작업 현장: {e(hero['title'])}. 가운데 막대를 좌우로 움직여 비교해 보세요.</p>
    </div>
  </div>
</section>

<section class="section">
  <div class="wrap">
    <div class="section-head"><span class="eyebrow">Before &amp; After</span><h2>작업 전과 후</h2>
      <p>강산자원이 직접 작업한 현장 사진입니다. 전후 사진 {len(CASES)}건은 <a href="cases/index.html">작업사례</a>에서 보실 수 있습니다.</p></div>
    <div class="cases">{cases}</div>
  </div>
</section>

{f'''<section class="section band">
  <div class="wrap">
    <div class="section-head"><span class="eyebrow">Videos</span><h2>현장 영상</h2><p>인스타그램에 올린 작업 영상입니다. <a href="videos.html">영상 더 보기</a></p></div>
    <div class="videos">{videos}</div>
  </div>
</section>''' if videos else ''}

<section class="section">
  <div class="wrap">
    <div class="section-head"><span class="eyebrow">About</span><h2>강산자원은 이런 업체입니다</h2>
      <p>서울 은평구 증산동에 본사를 둔 폐기물 처리·실내철거 전문업체입니다. 가정, 사무실, 상가, 공장과 창고에서 나오는 폐기물을 수거하고, 쓰레기집 정리부터 철거와 원상복구까지 한 팀이 진행합니다.</p></div>
    {sheet(C.FACTS)}
  </div>
</section>

<section class="section band">
  <div class="wrap">
    <div class="section-head"><span class="eyebrow">Services</span><h2>맡기실 수 있는 일</h2>
      <p>가정의 가구 한 점부터 쓰레기집, 상가 폐업 철거, 공사 현장 폐기물까지 강산자원이 처리하는 {len(SERVICES)}가지 작업입니다.</p></div>
    <div class="svc-grid">{svc_items}</div>
  </div>
</section>

<section class="section">
  <div class="wrap">
    <div class="section-head"><span class="eyebrow">Items</span><h2>버리실 물건으로 찾기</h2><p>품목마다 옮기는 방법과 주의할 점이 다릅니다.</p></div>
    <ul class="chips chips-lg">{item_chips}</ul>
  </div>
</section>

<section class="section band">
  <div class="wrap">
    <div class="section-head"><span class="eyebrow">Why</span><h2>강산자원에 맡기는 이유</h2></div>
    <div class="why">{why}</div>
  </div>
</section>

<section class="section">
  <div class="wrap split">
    <div>
      <div class="section-head"><span class="eyebrow">Process</span><h2>견적부터 마무리까지</h2>
        <p>가격은 작업마다 물량과 현장 조건이 달라 사진을 보고 정합니다. 견적은 무료입니다.</p></div>
      {steps_html(C.PROCESS)}
      <p style="margin-top:16px"><a href="estimate.html">사진 찍는 요령과 비용이 정해지는 기준 보기 →</a></p>
    </div>
    <aside class="aside">{cta_card()}</aside>
  </div>
</section>

{f'''<section class="section band">
  <div class="wrap">
    <div class="section-head"><span class="eyebrow">Daily</span><h2>강산 일상</h2><p>블로그에 올린 최근 현장 이야기입니다. <a href="daily/index.html">전체 보기</a></p></div>
    <div class="posts">{posts}</div>
  </div>
</section>''' if posts else ''}

<section class="section">
  <div class="wrap">
    <div class="section-head"><span class="eyebrow">Vehicles</span><h2>1톤 트럭부터 집게차, 사다리차까지 직접 보유</h2><p>현장에 맞는 장비를 바로 보낼 수 있어 일정이 밀리지 않습니다.</p></div>
    <div class="vehicles">{vehicles}</div>
  </div>
</section>

<section class="section band">
  <div class="wrap">
    <div class="section-head"><span class="eyebrow">Area</span><h2>서울·경기·인천 어디든 출동합니다</h2><p>본사(은평구 증산동)를 기준으로 수도권 전 지역에 출동하며, 수도권은 당일 출동도 가능합니다.</p></div>
    <div class="table-wrap"><table><tbody>{area_rows}</tbody></table></div>
  </div>
</section>

<section class="section">
  <div class="wrap">
    <div class="section-head"><span class="eyebrow">Reviews</span><h2>고객 후기</h2><p>당근 동네업체에 남겨주신 후기 중 일부입니다. <a href="reviews.html">후기 더 보기</a></p></div>
    <div class="reviews">{reviews}</div>
  </div>
</section>

<section class="section band">
  <div class="wrap">
    <div class="section-head"><span class="eyebrow">FAQ</span><h2>자주 묻는 질문</h2></div>
    {faq_html(C.GENERAL_FAQS[:8], open_first=True)}
    <p style="margin-top:16px"><a href="faq.html">질문 전체 보기 →</a></p>
  </div>
</section>
"""
    page(p, "강산자원", "서울·경기·인천 폐기물 처리 30년, 강산자원. 대형폐기물·이사짐·유품정리·쓰레기집 정리, 사진 무료 견적 010-6338-4016",
         main, head_title="강산자원 | 30년 경력 폐기물 처리·쓰레기집 정리",
         ld=[faq_ld(C.GENERAL_FAQS[:8])], og_photo=case_photo("b275"), og_sub="서울·경기·인천 폐기물 처리 30년. 대표 직접 출동, 사진 무료 견적.",
         images=case_imgs(home_cases))


# ---------------------------------------------------------------- 서비스
def build_services():
    p = "services/index.html"
    items = "".join(
        f'<a class="svc" href="{s["slug"]}.html"><h3><small>{i + 1:02d}</small>{e(s["name"])}</h3><p>{e(s["short"])}</p><span class="more">자세히 보기 →</span></a>'
        for i, s in enumerate(SERVICES))
    page(p, "서비스 안내", f"강산자원 폐기물 처리 서비스 {len(SERVICES)}가지: " + ", ".join(s["name"] for s in SERVICES) + ".",
         f'<section class="section"><div class="wrap"><div class="svc-grid">{items}</div></div></section>',
         head("서비스 안내", "가구 한 점부터 쓰레기집, 상가 폐업 철거, 공사 현장 폐기물까지 강산자원이 처리하는 일입니다."),
         crumbs=[(p, "서비스")], og_sub="가정·사무실·상가·사업장 폐기물, 쓰레기집, 철거까지",
         ld=[{"@type": "ItemList", "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": s["name"], "url": url(f"services/{s['slug']}.html")} for i, s in enumerate(SERVICES)]}])

    for s in SERVICES:
        p = f"services/{s['slug']}.html"
        cs = cases_for_service(s["slug"], 6)
        intro = "".join(f"<p>{e(t)}</p>" for t in s["intro"])
        chips = "".join(f"<li>{e(t)}</li>" for t in s["items"])
        sits = "".join(f"<li>{e(t)}</li>" for t in s["situations"])
        notes = "".join(f"<div><h3>{e(t)}</h3><p>{e(d)}</p></div>" for t, d in s["notes"])
        selfs = "".join(f"<div><h3>{e(t)}</h3><p>{e(d)}</p></div>" for t, d in s.get("self", []))
        faqs = s["faqs"] + s["more_faqs"]
        rel_items = [i for i in ITEMS if i["service"] == s["slug"]]
        guides = [g for g in GUIDES if s["slug"] in g["related"]]
        others = "".join(f'<li><a href="{o["slug"]}.html">{e(o["name"])}</a></li>' for o in SERVICES if o is not s)
        summary = f"강산자원은 서울·경기·인천에서 {s['name']} 작업을 합니다. {s['short']} 대표가 직접 출동하고 본사 직원이 작업하며, 사진을 보내주시면 무료로 견적을 드립니다."
        main = f"""
<section class="section">
  <div class="wrap split">
    <article class="prose">
      <p class="note"><strong>요약</strong> {e(summary)}</p>
      <h2>이런 경우라면 맡겨주세요</h2>
      <ul class="checklist">{sits}</ul>
      <h2>{e(s['name'])}, 왜 어려울까요</h2>
      {intro}
      <h2>이런 물건을 처리합니다</h2>
      <ul class="chips">{chips}</ul>
      {f'<h2>맡기기 전에 직접 하실 수 있는 준비</h2><div class="why why-2">{selfs}</div>' if selfs else ''}
      {f'<h2>강산자원은 이렇게 진행합니다</h2>{steps_html(s["approach"])}' if s.get("approach") else ''}
      <h2>작업 전에 알아두시면 좋은 점</h2>
      <div class="why why-2">{notes}</div>
      <h2>비용 안내</h2>
      <p>{e(s['name'])} 비용은 물량, 품목, 층수와 엘리베이터 유무, 분해·철거 여부, 차량 진입 여건에 따라 달라집니다. 그래서 고정 가격표 대신 현장 사진을 보고 무료로 견적을 드립니다. <a href="../estimate.html">비용이 정해지는 기준과 사진 찍는 요령</a>을 참고해 주세요.</p>
    </article>
    <aside class="aside">
      {cta_card()}
      <div class="note"><strong>다른 서비스</strong><ul>{others}</ul></div>
    </aside>
  </div>
</section>
{f'''<section class="section band"><div class="wrap"><div class="section-head"><h2>{e(s['name'])} 작업사례</h2><p>강산자원이 직접 작업한 현장의 전후 사진입니다.</p></div><div class="cases">{"".join(case_card(p, c) for c in cs)}</div></div></section>''' if cs else ''}
<section class="section"><div class="wrap"><div class="section-head"><h2>{e(s['name'])} 자주 묻는 질문</h2></div>{faq_html(faqs, open_first=True)}</div></section>
{f'<section class="section band"><div class="wrap"><div class="section-head"><h2>관련 품목</h2></div>{link_cards(p, [(f"items/{i['slug']}.html", i["name"], i["sub"]) for i in rel_items])}</div></section>' if rel_items else ''}
{f'<section class="section"><div class="wrap"><div class="section-head"><h2>함께 읽으면 좋은 글</h2></div>{link_cards(p, [(f"guide/{g['slug']}.html", g["title"], g["desc"]) for g in guides])}</div></section>' if guides else ''}
"""
        desc = f"{s['name']}, 30년 경력 강산자원. {SVC_SUB[s['slug']]}. 서울·경기·인천 출동, 사진 무료 견적 010-6338-4016"
        ld = [{"@type": "Service", "name": s["name"], "serviceType": s["keywords"][0], "description": s["short"] + " " + " ".join(s["intro"]),
               "provider": {"@id": url("index.html") + "#business"},
               "areaServed": [{"@type": "AdministrativeArea", "name": n} for n in ("서울특별시", "경기도", "인천광역시")],
               "keywords": ", ".join(s["keywords"]),
               "image": [url(x) for x in case_imgs(cs[:2])],
               "offers": {"@type": "Offer", "description": "현장 사진 기반 무료 견적", "priceCurrency": "KRW"}}, faq_ld(faqs)]
        page(p, s["name"], desc, main, head(s["name"], s["short"], "서비스"),
             crumbs=[("services/index.html", "서비스"), (p, s["name"])], ld=ld,
             og_photo=case_photo(cs[0]["id"]) if cs else None, og_sub=SVC_SUB[s["slug"]] + " · 사진 무료 견적",
             images=case_imgs(cs))


# ---------------------------------------------------------------- 품목별
def build_items():
    p = "items/index.html"
    page(p, "품목별 수거", "장롱, 침대·매트리스, 소파, 냉장고, 에어컨, 세탁기, 피아노, 운동기구, 사무용 가구, 파티션, 화분, 파렛트 등 품목별 수거 방법과 주의할 점.",
         f'<section class="section"><div class="wrap">{link_cards(p, [("items/" + i["slug"] + ".html", i["name"], i["sub"]) for i in ITEMS])}</div></section>',
         head("품목별 수거", "버리실 물건을 고르면 옮기는 방법과 주의할 점, 비슷한 작업사례를 보실 수 있습니다."),
         crumbs=[(p, "품목별 수거")], og_sub="장롱·침대·냉장고·에어컨·피아노 등 품목별 안내")
    for it in ITEMS:
        p = f"items/{it['slug']}.html"
        s = SVC[it["service"]]
        cs = [CASE[i] for i in it["cases"] if i in CASE] or cases_for_service(it["service"], 3)
        intro = "".join(f"<p>{e(t)}</p>" for t in it["intro"])
        pts = "".join(f"<li>{e(t)}</li>" for t in it["points"])
        others = "".join(f'<li><a href="{o["slug"]}.html">{e(o["name"])}</a></li>' for o in ITEMS if o is not it)
        summary = f"강산자원은 서울·경기·인천에서 {it['name']} 수거를 합니다. {it['sub']}. 사진을 보내주시면 무료로 견적을 드립니다."
        main = f"""
<section class="section">
  <div class="wrap split">
    <article class="prose">
      <p class="note"><strong>요약</strong> {e(summary)}</p>
      {intro}
      <h2>강산자원이 처리하는 범위</h2>
      <ul class="checklist">{pts}</ul>
      <h2>버리는 방법 비교</h2>
      <div class="table-wrap"><table>
        <thead><tr><th scope="col"></th><th scope="col">구청 대형폐기물 신고</th><th scope="col">강산자원 방문 수거</th></tr></thead>
        <tbody>
          <tr><th scope="row">신고·스티커</th><td>직접 신고하고 수수료 납부</td><td>필요 없음</td></tr>
          <tr><th scope="row">집 밖까지 운반</th><td>직접 옮겨야 함</td><td>직원이 집 안에서 반출</td></tr>
          <tr><th scope="row">분해</th><td>직접 분해</td><td>현장에서 분해</td></tr>
          <tr><th scope="row">다른 짐 함께</th><td>품목별로 각각 신고</td><td>가구·가전·잔짐 한 번에</td></tr>
          <tr><th scope="row">비용</th><td>품목별 수수료(지자체마다 다름)</td><td>사진 보고 무료 견적</td></tr>
        </tbody></table></div>
      <p>한두 개를 직접 옮길 수 있다면 구청 신고가 경제적입니다. 무겁거나 양이 많고, 일정이 정해져 있다면 방문 수거가 편합니다.</p>
      <h2>자주 묻는 질문</h2>
      {faq_html(it['faqs'], open_first=True)}
      <p>관련 서비스: <a href="../services/{s['slug']}.html">{e(s['name'])}</a></p>
    </article>
    <aside class="aside">{cta_card()}<div class="note"><strong>다른 품목</strong><ul>{others}</ul></div></aside>
  </div>
</section>
{f'''<section class="section band"><div class="wrap"><div class="section-head"><h2>관련 작업사례</h2></div><div class="cases">{"".join(case_card(p, c) for c in cs)}</div></div></section>''' if cs else ''}
"""
        page(p, f"{it['name']} 수거", f"{it['name']} 수거, 30년 경력 강산자원. {it['sub']}. 서울·경기·인천 방문 수거, 사진 무료 견적",
             main, head(f"{it['name']} 수거", it["sub"], "품목별 수거"),
             crumbs=[("items/index.html", "품목별 수거"), (p, it["name"])],
             ld=[{"@type": "Service", "name": f"{it['name']} 수거", "provider": {"@id": url("index.html") + "#business"}, "description": " ".join(it["intro"])}, faq_ld(it["faqs"])],
             og_photo=case_photo(cs[0]["id"], "before") if cs else None, og_sub=it["sub"], images=case_imgs(cs))


# ---------------------------------------------------------------- 작업사례
def build_cases():
    p = "cases/index.html"
    cat_links = [(f"cases/{k}.html", f"{n} ({sum(1 for c in CASES if c['cat'] == k)}건)", d) for k, n, d in CATS]
    filters = '<button type="button" data-filter="all" aria-pressed="true">전체</button>' + "".join(
        f'<button type="button" data-filter="{k}" aria-pressed="false">{e(n)}</button>' for k, n, _ in CATS)
    cards = "".join(case_card(p, c, lazy=i > 3) for i, c in enumerate(CASES))
    main = f"""
<section class="section"><div class="wrap">
  <div class="section-head"><h2>분류별로 보기</h2></div>
  {link_cards(p, cat_links)}
</div></section>
<section class="section band"><div class="wrap">
  <div class="section-head"><h2>전체 작업사례 {len(CASES)}건</h2><p>강산자원이 30년 동안 직접 처리한 현장 중 일부입니다. 매년 250곳 이상의 가정집, 사무실, 철거·폐업 현장을 방문합니다.</p></div>
  <div class="filters" data-filter-group="case-list" role="group" aria-label="작업 종류로 보기">{filters}</div>
  <div class="cases" id="case-list">{cards}</div>
</div></section>"""
    gallery = [{"@type": "ImageObject", "contentUrl": url(f"images/cases/{c['id']}-{side}.jpg"), "name": f"{c['title']} {lab}", "description": c["desc"]}
               for c in CASES for side, lab in (("before", "작업 전"), ("after", "작업 후"))]
    page(p, "작업사례", f"강산자원이 직접 작업한 폐기물 수거·쓰레기집 정리·철거 현장 {len(CASES)}곳의 작업 전후 사진. 이사 폐기물, 유품정리, 가구·가전 수거, 사무실, 폐업 정리.",
         main, head("작업사례", f"강산자원이 직접 작업한 현장의 작업 전과 후 사진 {len(CASES)}건입니다."),
         crumbs=[(p, "작업사례")], ld=[{"@type": "ImageGallery", "name": "강산자원 작업사례", "image": gallery}],
         og_photo=case_photo("g000"), og_sub=f"직접 작업한 현장 전후 사진 {len(CASES)}건", images=case_imgs(CASES))
    for k, n, d in CATS:
        p = f"cases/{k}.html"
        cs = [c for c in CASES if c["cat"] == k]
        svc_ids = list(dict.fromkeys(c["service"] for c in cs))
        rel_svc = link_cards(p, [(f"services/{sid}.html", SVC[sid]["name"], SVC[sid]["short"]) for sid in svc_ids])
        others = " · ".join(f'<a href="{kk}.html">{e(nn)}</a>' for kk, nn, _ in CATS if kk != k)
        main = f"""
<section class="section"><div class="wrap">
  <p class="note" style="margin-bottom:28px"><strong>{e(n)} 사례 {len(cs)}건</strong> {e(d)} 다른 분류: {others}</p>
  <div class="cases">{"".join(case_card(p, c, lazy=i > 3) for i, c in enumerate(cs))}</div>
</div></section>
<section class="section band"><div class="wrap"><div class="section-head"><h2>관련 서비스</h2></div>{rel_svc}</div></section>"""
        page(p, f"{n} 작업사례", f"{n} 작업 전후 사진 {len(cs)}건. {d} 서울·경기·인천 30년 경력 강산자원.",
             main, head(f"{n} 작업사례", d, "작업사례"),
             crumbs=[("cases/index.html", "작업사례"), (p, n)], og_photo=case_photo(cs[0]["id"]),
             og_sub=f"직접 작업한 {n} 현장 {len(cs)}건", images=case_imgs(cs))


# ---------------------------------------------------------------- 영상
def build_videos():
    if not INSTA:
        return
    p = "videos.html"
    cards = "".join(insta_card(p, v, lazy=i > 3) for i, v in enumerate(INSTA))
    main = f"""<section class="section"><div class="wrap">
  <div class="prose" style="margin-bottom:28px"><p>강산자원 인스타그램(<a href="{B['instagram']}" target="_blank" rel="noopener">@gangsan_30</a>)에 올린 현장 영상과 사진입니다. 썸네일을 누르면 영상이 재생됩니다. 새 게시물은 홈페이지에 자동으로 추가됩니다.</p></div>
  <div class="videos">{cards}</div>
  <div class="btn-row" style="margin-top:28px"><a class="btn btn-ghost" href="{B['instagram']}" target="_blank" rel="noopener">인스타그램에서 전체 보기</a></div>
</div></section>"""
    vids = [{"@type": "VideoObject" if v["video"] else "ImageObject", "name": insta_title(v), "description": v["caption"][:300],
             "thumbnailUrl": url(f"images/insta/{v['code']}.jpg"), "uploadDate": v["date"], "contentUrl": v["url"], "embedUrl": v["url"] + "embed/"} for v in INSTA]
    page(p, "현장 영상", "강산자원 인스타그램 현장 영상: 유품정리, 이사 폐기물, 가구·가전 수거, 에어컨 철거 등 실제 작업 모습.",
         main, head("현장 영상", "실제 작업 현장을 영상으로 보여드립니다."), crumbs=[(p, "현장 영상")], ld=vids,
         og_photo=os.path.join(DATA, "insta_img", INSTA[0]["code"] + ".jpg"), og_sub="유품정리·이사 폐기물·가구 수거 현장 영상")


def insta_title(v):
    lines = [ln.strip() for ln in v["caption"].splitlines() if ln.strip() and not ln.strip().startswith("#")]
    return re.sub(r"^제목\s*:\s*", "", lines[0] if lines else "강산자원 작업 영상")


# ---------------------------------------------------------------- 강산 일상 (블로그 연동)
def blog_block_html(path, b):
    if b["t"] == "p":
        return f"<p>{e(b['text'])}</p>"
    if b["t"] == "h":
        return f"<h2>{e(b['text'])}</h2>"
    if b["t"] == "quote":
        return f"<blockquote class=\"note\"><p>{e(b['text'])}</p></blockquote>"
    if b["t"] == "img":
        cap = f"<figcaption>{e(b['alt'])}</figcaption>" if b["alt"] else ""
        return f'<figure class="post-img">{img(path, "images/daily/" + b["src"], b["alt"] or "강산자원 현장 사진", 900, 900)}{cap}</figure>'
    if b["t"] == "table":
        rows = "".join("<tr>" + "".join(f"<td>{e(c)}</td>" for c in r) + "</tr>" for r in b["rows"])
        return f'<div class="table-wrap"><table><tbody>{rows}</tbody></table></div>'
    return ""


def build_daily():
    p = "daily/index.html"
    cards = "".join(blog_card(p, x) for x in BLOG)
    main = f"""<section class="section"><div class="wrap">
  <div class="prose" style="margin-bottom:28px"><p>강산자원 네이버 블로그(<a href="https://blog.naver.com/{BLOG_ID}" target="_blank" rel="noopener">blog.naver.com/{BLOG_ID}</a>)에 올라오는 현장 이야기입니다. 블로그에 새 글이 올라오면 이 페이지에도 자동으로 추가됩니다.</p></div>
  <div class="posts">{cards or '<p>아직 글이 없습니다.</p>'}</div>
</div></section>"""
    page(p, "강산 일상", "강산자원 블로그 현장 이야기. 가정집 폐기물, 이사 후 짐 정리, 유품정리, 집게차 수거 현장 기록.",
         main, head("강산 일상", "매일 다니는 현장의 이야기를 블로그와 함께 전합니다."), crumbs=[(p, "강산 일상")],
         og_photo=os.path.join(DATA, "blog_img", blog_thumb(BLOG[0]).split("/")[-1]) if BLOG and blog_thumb(BLOG[0]) else None,
         og_sub="블로그와 연동되는 강산자원 현장 이야기",
         ld=[{"@type": "ItemList", "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": x["title"], "url": url(f"daily/{x['id']}.html")} for i, x in enumerate(BLOG)]}])
    for i, x in enumerate(BLOG):
        p = f"daily/{x['id']}.html"
        body = "".join(blog_block_html(p, b) for b in x["blocks"]) or f"<p>{e(x['summary'])}</p>"
        nav = []
        if i > 0:
            nav.append(f'<a href="{BLOG[i - 1]["id"]}.html"><b>다음 글</b><span>{e(BLOG[i - 1]["title"])}</span></a>')
        if i < len(BLOG) - 1:
            nav.append(f'<a href="{BLOG[i + 1]["id"]}.html"><b>이전 글</b><span>{e(BLOG[i + 1]["title"])}</span></a>')
        main = f"""<section class="section"><div class="wrap split">
  <article class="prose post-body">
    <p class="muted">{x['date']} · <a href="{x['url']}" target="_blank" rel="noopener">블로그 원문 보기 ↗</a></p>
    {body}
    <div class="link-list" style="margin-top:24px">{"".join(nav)}</div>
  </article>
  <aside class="aside">{cta_card()}</aside>
</div></section>"""
        th = blog_thumb(x)
        # 블로그 원문과 같은 글이므로 검색엔진에는 원문만 노출되도록 noindex + 원문 canonical
        page(p, x["title"], x["summary"][:150], main, head(x["title"], x["summary"][:90], "강산 일상"),
             crumbs=[("daily/index.html", "강산 일상"), (p, x["title"][:24])], indexable=False, canonical=x["url"],
             og_photo=os.path.join(DATA, "blog_img", th.split("/")[-1]) if th else None, og_sub="강산 일상 · 현장 이야기")


# ---------------------------------------------------------------- 견적, 회사, 지역, 가이드, 기타
def build_estimate():
    p = "estimate.html"
    guide = "".join(f"<div><h3>{e(t)}</h3><p>{e(d)}</p></div>" for t, d in C.PHOTO_GUIDE)
    factors = "".join(f"<tr><th scope=\"row\">{e(t)}</th><td>{e(d)}</td></tr>" for t, d in C.PRICE_FACTORS)
    main = f"""
<section class="section">
  <div class="wrap split">
    <article class="prose">
      <p class="note"><strong>요약</strong> 강산자원은 작업마다 물량과 현장 조건이 달라 고정 가격표를 두지 않습니다. 현장 사진을 카카오톡 채널 ‘강산자원’ 또는 문자(010-6338-4016)로 보내주시면 무료로 견적을 드립니다. 견적을 받았다고 꼭 맡기셔야 하는 것은 아닙니다.</p>
      <h2>견적부터 작업까지</h2>
      {steps_html(C.PROCESS)}
      <h2>사진은 이렇게 찍어주세요</h2>
      <div class="why why-2">{guide}</div>
      <h2>사진과 함께 알려주실 내용</h2>
      <ul class="checklist">
        <li>주소 (동까지만 알려주셔도 됩니다)</li><li>층수와 엘리베이터 유무</li><li>건물 앞 차량 정차 가능 여부</li>
        <li>희망 날짜와 시간대</li><li>철거가 필요한 부분 (싱크대, 타일, 칸막이 등)</li><li>석면, 폐유, 화학 약품 등 특수 폐기물이 있는지</li>
      </ul>
      <h2>비용은 이런 기준으로 정해집니다</h2>
      <div class="table-wrap"><table><thead><tr><th scope="col">기준</th><th scope="col">내용</th></tr></thead><tbody>{factors}</tbody></table></div>
      <p>같은 원룸 짐이라도 엘리베이터가 있는 건물과 4층 계단 건물은 필요한 인원이 다릅니다. 고정 가격표보다 사진 견적이 정확한 이유입니다. 사진에 없던 짐이 현장에서 추가되면 작업 전에 다시 안내해 드립니다.</p>
    </article>
    <aside class="aside">{cta_card()}</aside>
  </div>
</section>"""
    page(p, "무료견적·작업 절차", "강산자원 폐기물 처리 비용은 사진을 보고 무료로 견적을 드립니다. 견적 받는 방법, 사진 찍는 요령, 비용이 정해지는 기준(물량·품목·층수·철거 여부).",
         main, head("무료견적·작업 절차", "사진 몇 장이면 견적이 나옵니다. 비용이 어떻게 정해지는지, 어떤 사진을 보내면 되는지 정리했습니다."),
         crumbs=[(p, "무료견적")], og_sub="사진만 보내면 무료 견적",
         ld=[{"@type": "HowTo", "name": "강산자원 사진 무료 견적 받는 방법", "step": [{"@type": "HowToStep", "position": i + 1, "name": t, "text": d} for i, (t, d) in enumerate(C.PROCESS)]}])


def build_about():
    p = "about.html"
    why = "".join(f"<div><h3>{e(t)}</h3><p>{e(d)}</p></div>" for t, d in C.WHY)
    vehicles = "".join(f'<div class="vehicle"><b>{e(v["name"])}</b><p><strong>주요 작업</strong> {e(v["use"])}</p><p>{e(v["note"])}</p></div>' for v in C.VEHICLES)
    main = f"""
<section class="section">
  <div class="wrap split">
    <article class="prose">
      <p class="note"><strong>요약</strong> 강산자원은 서울 은평구 증산동에 본사를 둔 폐기물 처리·실내철거 전문업체입니다. 30년 동안 10,000곳 이상의 현장을 다녔고, 대표가 직접 출동해 본사 직원과 함께 작업합니다.</p>
      <h2>30년 동안 한 가지 일</h2>
      <p>강산자원은 폐기물 처리 한 분야에서 30년을 일했습니다. 매년 250곳 이상의 가정집, 사무실, 철거·인테리어·폐업 현장을 방문합니다. 가정집 가구 한 점부터 쓰레기집 정리, 학원 폐업, 식당 원상복구, 공장 창고 정리까지 다니며 쌓은 경험으로 사진만 봐도 물량과 필요한 인원, 차량을 판단합니다.</p>
      <p>현장을 많이 다녀본 만큼 작업이 빠르고, 처음 계획과 실제 작업이 크게 달라지지 않습니다. 견적 때 안내한 내용 그대로 작업하는 것이 강산자원의 원칙입니다.</p>
      <h2>대표가 직접 현장에 갑니다</h2>
      <p>모든 현장에 대표가 직접 나가 작업을 지휘합니다. 현장 규모에 따라 본사 직원 3~8명이 함께 투입되고, 일을 다른 업체에 넘기지 않습니다.</p>
      <h2>고객의 일정에 맞춥니다</h2>
      <p>100% 예약제로 운영해 약속한 시간에 정확히 도착합니다. 주말과 공휴일에도 예약을 받아 작업합니다. 상담은 24시간, 연중무휴로 받습니다.</p>
      <h2>강산자원의 원칙</h2>
      <ul class="checklist"><li>사진을 보고 정직하게 견적을 드립니다.</li><li>약속한 시간에 도착합니다.</li><li>집과 건물이 상하지 않도록 반출 동선을 먼저 확인합니다.</li><li>폐기물을 반출한 뒤 바닥 잔여물까지 정리합니다.</li><li>처리할 수 없는 품목은 미리 솔직하게 안내합니다.</li></ul>
    </article>
    <aside class="aside">{sheet(C.FACTS[:9], title="회사 정보", sub="")}</aside>
  </div>
</section>
<section class="section band"><div class="wrap"><div class="section-head"><h2>강산자원에 맡기는 이유</h2></div><div class="why">{why}</div></div></section>
<section class="section" id="vehicles"><div class="wrap"><div class="section-head"><h2>보유 차량</h2><p>1톤 트럭부터 집게차, 사다리차까지 직접 보유하고 있어 현장에 맞는 장비를 바로 보냅니다.</p></div><div class="vehicles">{vehicles}</div></div></section>"""
    page(p, "회사소개", "강산자원은 서울 은평구 증산동에 본사를 둔 30년 경력 폐기물 처리·실내철거 전문업체입니다. 10,000곳 이상 출동, 대표 직접 출동, 본사 직원 3~8명, 1톤 트럭·집게차·사다리차 보유.",
         main, head("회사소개", "폐기물 처리 30년, 10,000곳 이상의 현장. 대표가 직접 출동하는 강산자원입니다."),
         crumbs=[(p, "회사소개")], ld=[{"@type": "AboutPage", "name": "강산자원 회사소개", "url": url(p)}], og_sub="30년 경력 · 대표 직접 출동 · 차량 직접 보유")


def build_areas():
    p = "areas/index.html"
    page(p, "출동지역", "강산자원은 서울 25개 구, 경기도, 인천광역시 등 수도권 전 지역으로 출동합니다. 본사 서울 은평구 증산동, 수도권 당일 출동 가능.",
         f'<section class="section"><div class="wrap"><div class="prose" style="margin-bottom:24px"><p>강산자원 본사는 서울 은평구 증산로5길 14(증산역 인근)에 있습니다. 서울 25개 구 전체와 경기도, 인천광역시 등 수도권 전 지역으로 출동합니다.</p></div>{link_cards(p, [("areas/" + k + ".html", a["full"] + " 폐기물 처리", a["lead"]) for k, a in C.AREAS.items()])}</div></section>',
         head("출동지역", "서울·경기·인천 수도권 전 지역으로 출동합니다."), crumbs=[(p, "출동지역")], og_sub="서울 25개 구 · 경기 · 인천 전 지역")
    for k, a in C.AREAS.items():
        p = f"areas/{k}.html"
        body = "".join(f"<p>{e(t)}</p>" for t in a["body"])
        chips = "".join(f"<li>{e(d)}</li>" for d in a["districts"])
        svc = "".join(f'<li><a href="../services/{s["slug"]}.html">{e(a["name"])} {e(s["name"])}</a></li>' for s in SERVICES)
        main = f"""<section class="section"><div class="wrap split"><article class="prose">
      <p class="note"><strong>요약</strong> 강산자원은 {e(a['full'])} 전 지역에서 대형폐기물 수거, 이사 폐기물, 유품정리, 쓰레기집 정리·청소, 사무실·상가 원상복구, 실내철거를 합니다. 사진을 보내주시면 무료로 견적을 드립니다.</p>
      <p>{e(a['lead'])}</p>{body}
      <h2>{e(a['full'])} 출동 지역</h2><ul class="chips">{chips}</ul>
      <p class="muted">목록에 없는 지역도 출동합니다. 주소를 알려주시면 일정을 안내해 드립니다.</p>
      <h2>{e(a['name'])}에서 맡기실 수 있는 일</h2><ul>{svc}</ul>
    </article><aside class="aside">{cta_card()}</aside></div></section>"""
        page(p, f"{a['full']} 폐기물 처리", f"{a['full']} 대형폐기물·폐가구 수거, 이사 폐기물, 유품정리, 쓰레기집 정리, 상가 원상복구, 실내철거. {', '.join(a['districts'][:8])} 등 {a['name']} 전 지역 출동. 강산자원 010-6338-4016.",
             main, head(f"{a['full']} 폐기물 처리", a["lead"]), crumbs=[("areas/index.html", "출동지역"), (p, a["full"])],
             ld=[{"@type": "Service", "name": f"{a['full']} 폐기물 처리", "provider": {"@id": url("index.html") + "#business"},
                  "areaServed": {"@type": "AdministrativeArea", "name": a["full"], "containsPlace": [{"@type": "Place", "name": d} for d in a["districts"]]}}],
             og_sub=", ".join(a["districts"][:6]) + " 등 전 지역")


def build_guides():
    p = "guide/index.html"
    page(p, "폐기물 처리 가이드", "대형폐기물 버리는 법, 매트리스·폐가전 처리, 이사 폐기물 체크리스트, 쓰레기집 정리, 상가 원상복구, 유품정리 순서 등 30년 경력 강산자원이 정리한 안내.",
         f'<section class="section"><div class="wrap">{link_cards(p, [("guide/" + g["slug"] + ".html", g["title"], g["desc"]) for g in GUIDES])}</div></section>',
         head("폐기물 처리 가이드", "30년 동안 현장에서 가장 많이 받은 질문을 정리했습니다."), crumbs=[(p, "폐기물 가이드")], og_sub="현장 경험으로 쓴 폐기물 처리 안내")
    for g in GUIDES:
        p = f"guide/{g['slug']}.html"
        secs = "".join(f"<h2>{e(h)}</h2>" + "".join(f"<p>{e(t)}</p>" for t in ps) for h, ps in g["sections"])
        cs = cases_for_service(g["related"][0], 2)
        main = f"""<section class="section"><div class="wrap split"><article class="prose">
      <p class="note"><strong>요약</strong> {e(g['desc'])}</p>{secs}
      <p class="muted">이 글은 일반적인 안내입니다. 수수료와 배출 기준은 지자체마다 다를 수 있으니 거주지 구청 안내를 함께 확인하세요.</p>
      <h2>관련 서비스</h2>{link_cards(p, [(f"services/{s}.html", SVC[s]["name"], SVC[s]["short"]) for s in g["related"]])}
    </article><aside class="aside">{cta_card()}</aside></div></section>
{f'''<section class="section band"><div class="wrap"><div class="section-head"><h2>관련 작업사례</h2></div><div class="cases">{"".join(case_card(p, c) for c in cs)}</div></div></section>''' if cs else ''}"""
        page(p, g["title"], g["desc"], main, head(g["title"], g["desc"], "폐기물 처리 가이드"),
             crumbs=[("guide/index.html", "폐기물 가이드"), (p, g["title"])],
             ld=[{"@type": "Article", "headline": g["title"], "description": g["desc"], "inLanguage": "ko-KR", "image": url("images/og/" + p.replace("/", "-").replace(".html", "") + ".jpg"),
                  "author": {"@id": url("index.html") + "#business"}, "publisher": {"@id": url("index.html") + "#business"}, "dateModified": TODAY, "mainEntityOfPage": url(p)}],
             og_photo=case_photo(cs[0]["id"], "before") if cs else None, og_sub="강산자원 폐기물 처리 가이드")


# ---------------------------------------------------------------- 전후 사진 묶음 (칼럼 갤러리, 검색 이미지용)
def make_pair_images():
    """사례마다 작업 전·후를 나란히 붙인 정사각형 사진(900x900)을 만든다."""
    out_dir = os.path.join(DIST, "images", "pair")
    os.makedirs(out_dir, exist_ok=True)
    for c in CASES:
        im = Image.new("RGB", (900, 900), "#1c5a3e")
        paste_pair(im, (case_photo(c["id"], "before"), case_photo(c["id"], "after")), (0, 0, 900, 900))
        im.save(os.path.join(out_dir, f"{c['id']}.jpg"), quality=84, optimize=True, progressive=True)


def pick_cases(cats, seed, n=6, prefer=(), words=()):
    """주제·지역에 맞는 사례를 고른다. 주제어가 들어간 사례를 먼저, 그다음 분류가 맞는 사례를
    페이지마다 시작 위치를 달리해 고르므로 같은 사진이 반복되지 않는다."""
    k0 = int.from_bytes(seed.encode("utf-8"), "little")
    out = [CASE[i] for i in prefer if i in CASE]
    if words:
        hit = [c for c in CASES if c not in out and any(w in c["title"] + c["desc"] for w in words)]
        out += hit[k0 % max(1, len(hit)):] + hit[:k0 % max(1, len(hit))]
    if cats:
        pool = [c for c in CASES if c["cat"] in cats and c not in out]
        k = k0 % max(1, len(pool))
        out += pool[k:] + pool[:k]
    else:  # 지역 페이지: 분류를 섞어서 한 장씩
        order = ["household", "moving", "trash", "office", "estate", "demolition", "store", "outdoor"]
        by = {c: [x for x in CASES if x["cat"] == c and x not in out] for c in order}
        i = 0
        while len(out) < n and any(by.values()):
            c = order[(i + k0) % len(order)]
            if by[c]:
                lst = by[c]
                out.append(lst.pop(k0 % len(lst)))
            i += 1
    if len(out) < n:
        out += [c for c in CASES if c not in out]
    return out[:n]


def pair_gallery(path, cases, place):
    figs = "".join(
        f'<figure><a href="{rel(path, "cases/" + c["cat"] + ".html")}"><img src="{rel(path, "images/pair/" + c["id"] + ".jpg")}" '
        f'alt="{e(place)} {e(c["title"])} 작업 전후 사진" width="900" height="900" decoding="async"></a>'
        f'<figcaption>{e(c["title"])}</figcaption></figure>' for c in cases)
    return f'<div class="pair-gallery">{figs}</div>'


def kw_index(groups, label_of):
    chips = "".join(f'<li><a href="#k{i + 1}">{e(label_of(g))}</a></li>' for i, g in enumerate(groups))
    return f'<nav class="kw-index" aria-label="이 페이지의 주제"><ul class="chips">{chips}</ul></nav>'


# ---------------------------------------------------------------- 폐기물 칼럼 (주제별)
def build_columns(topic_kws):
    p = "column/index.html"
    blocks = ""
    for g, gname in CL.CD.GROUPS:
        ts = [t for t in CL.TOPIC.values() if t["group"] == g]
        blocks += f'<h2 style="margin-top:32px">{e(gname)}</h2>' + link_cards(p, [("column/" + t["slug"] + ".html", t["title"], t["lead"]) for t in ts])
    total = sum(len(v) for v in topic_kws.values())
    page(p, "폐기물 칼럼", f"매트리스·장롱·냉장고 버리는 법부터 철거, 폐업 정리, 쓰레기집, 폐기물 비용까지 {len(CL.TOPIC)}개 주제 칼럼. 30년 경력 강산자원.",
         f'<section class="section"><div class="wrap"><div class="prose"><p>현장에서 가장 많이 받는 질문 {total}가지를 주제별로 정리했습니다.</p></div>{blocks}</div></section>',
         head("폐기물 칼럼", "버리는 법, 철거, 폐업 정리, 비용까지 주제별로 정리했습니다."), crumbs=[(p, "폐기물 칼럼")],
         og_sub="버리는 법·철거·폐업·비용 주제별 안내")
    for t in CL.TOPIC.values():
        p = f"column/{t['slug']}.html"
        kws = topic_kws.get(t["slug"], [])
        groups = CL.topic_groups(t, kws)
        words = [w for slug, subs in CL.CD.RULES if slug == t["slug"] for w in subs]
        cs = pick_cases(t["cats"], t["slug"], 6, words=words)
        counts = {}
        secs = ""
        for i, g in enumerate(groups):
            kind = CL.split_kw(g[0], t["noun"])[1]
            n = counts.get(kind, 0); counts[kind] = n + 1
            h, txt = CL.topic_section(t, g[0], n)
            secs += f'<section class="kw-sec" id="k{i + 1}"><h3>{e(h)}</h3><p>{e(txt)}</p></section>'
        pts = "".join(f"<li>{e(x)}</li>" for x in t["points"])
        svc = SVC[t["service"]]
        related = [x for x in CL.TOPIC.values() if x["group"] == t["group"] and x is not t][:6]
        summary = f"{t['lead']} 강산자원은 서울·경기·인천에서 {t['noun']} 작업을 직접 하며, 사진을 보내주시면 무료로 견적을 드립니다."
        main = f"""
<section class="section">
  <div class="wrap">
    <p class="note" style="margin-bottom:20px"><strong>요약</strong> {e(summary)}</p>
    <h2 class="gallery-title">{e(t['noun'])} 현장 작업 전후</h2>
    {pair_gallery(p, cs, t['noun'])}
  </div>
</section>
<section class="section band">
  <div class="wrap split">
    <article class="prose">
      {"".join(f"<p>{e(x)}</p>" for x in t['intro'])}
      <h2>이 글에서 다루는 내용</h2>
      {kw_index(groups, lambda g: CL.topic_section(t, g[0])[0])}
      <h2>{e(t['noun'])} 자주 찾는 질문별 안내</h2>
      {secs}
      <h2>강산자원은 이렇게 처리합니다</h2>
      <ul class="checklist">{pts}</ul>
      <h2>직접 버릴 때 알아둘 점</h2>
      <p>{e(t['gov'])}</p>
      <h2>비용이 정해지는 기준</h2>
      <p>{e(t['cost'])} <a href="../estimate.html">사진 견적 받는 법</a>을 참고해 주세요.</p>
      <h2>작업 전 확인하세요</h2>
      <p>{e(t['care'])}</p>
      <h2>자주 묻는 질문</h2>
      {faq_html(t['faqs'], open_first=True)}
      <p>관련 서비스: <a href="../services/{svc['slug']}.html">{e(svc['name'])}</a></p>
    </article>
    <aside class="aside">{cta_card()}<div class="note"><strong>같은 분류 칼럼</strong><ul>{"".join(f'<li><a href="{x["slug"]}.html">{e(x["title"])}</a></li>' for x in related)}</ul></div></aside>
  </div>
</section>"""
        imgs = [f"images/pair/{c['id']}.jpg" for c in cs] + case_imgs(cs)
        ld = [{"@type": "Article", "headline": t["title"], "description": t["lead"], "inLanguage": "ko-KR",
               "keywords": ", ".join(kws), "image": [url(x) for x in imgs[:6]],
               "author": {"@id": url("index.html") + "#business"}, "publisher": {"@id": url("index.html") + "#business"},
               "dateModified": TODAY, "mainEntityOfPage": url(p)}, faq_ld(t["faqs"])]
        page(p, t["title"], f"{t['lead']} 30년 경력 강산자원, 사진 무료 견적.", main,
             head(t["title"], t["lead"], dict(CL.CD.GROUPS)[t["group"]]),
             crumbs=[("column/index.html", "폐기물 칼럼"), (p, t["title"])], ld=ld,
             og_photo=case_photo(cs[0]["id"]), og_sub=t["lead"][:60], images=imgs)


# ---------------------------------------------------------------- 지역별 안내
def local_title(r, items):
    rests = {it["rest"] for it in items}
    tail = "대형폐기물·폐기물 처리"
    if any("철거" in x for x in rests):
        tail = "대형폐기물·폐기물·철거"
    return f"{r['name']} {tail}"


def build_locals(region_kws):
    p = "local/index.html"
    blocks = ""
    for area in ("서울", "경기", "인천"):
        rs = [r for r in CL.REGION.values() if r["area"] == area]
        blocks += f'<h2 style="margin-top:32px">{area}</h2>' + link_cards(p, [("local/" + r["slug"] + ".html", local_title(r, region_kws[r["slug"]]), ", ".join(r["dongs"][:6])) for r in rs])
    page(p, "지역별 폐기물·철거 안내", f"서울·경기·인천 {len(CL.REGION)}개 지역별 대형폐기물 수거, 폐기물 처리, 철거 안내. 강산자원 본사 은평구 증산동.",
         f'<section class="section"><div class="wrap"><div class="prose"><p>지역마다 건물 유형과 동네 사정이 달라 작업 방식도 달라집니다. 동네를 고르면 그 지역 작업 안내와 실제 작업 사진을 보실 수 있습니다.</p></div>{blocks}</div></section>',
         head("지역별 폐기물·철거 안내", "서울·경기·인천 동네별 안내입니다."), crumbs=[(p, "지역별 안내")], og_sub="서울·경기·인천 지역별 안내")
    slugs = list(CL.REGION)
    for ri, r in enumerate(CL.REGION.values()):
        p = f"local/{r['slug']}.html"
        items = region_kws[r["slug"]]
        groups = CL.region_groups(items)
        prefer = [cid for cid, rs in M.CASE_REGION.items() if rs == r["slug"]]
        cs = pick_cases(None, r["slug"] + "x", 6, prefer)
        counts = {}
        secs = ""
        for i, g in enumerate(groups):
            kind = CL.RTYPE.get(g[0]["rest"], "general")
            n = counts.get(kind, 0); counts[kind] = n + 1
            h, txt = CL.region_section(r, g[0], n)
            kws = " · ".join(x["kw"] for x in g)
            secs += f'<section class="kw-sec" id="k{i + 1}"><h3>{e(h)}</h3><p>{e(txt)}</p><p class="kw-tags">{e(kws)}</p></section>'
        title = local_title(r, items)
        faqs = CL.region_faqs(r)
        near = [CL.REGION[slugs[(ri + d) % len(slugs)]] for d in (-2, -1, 1, 2)]
        near = [x for x in near if x["area"] == r["area"] and x is not r] or near
        dong_chips = "".join(f"<li>{e(d)}</li>" for d in r["dongs"])
        regional_cases = [c for c in cs if c["id"] in prefer]
        summary = f"강산자원은 {r['name']} 전 지역에서 대형폐기물 수거, 폐가구·폐가전 수거, 이사 폐기물, 쓰레기집 정리, 철거와 원상복구를 합니다. {CL.LD.NEAR_TEXT[r['near']]}"
        main = f"""
<section class="section">
  <div class="wrap">
    <p class="note" style="margin-bottom:20px"><strong>요약</strong> {e(summary)}</p>
    <h2 class="gallery-title">{e(r['name'])} 고객님이 맡기신 작업과 같은 현장 사진</h2>
    {pair_gallery(p, cs, r['name'])}
    {f'<p class="muted" style="margin-top:8px">앞의 {len(regional_cases)}장은 {e(r["name"])}에서 실제로 작업한 현장입니다.</p>' if regional_cases else ''}
  </div>
</section>
<section class="section band">
  <div class="wrap split">
    <article class="prose">
      <h2>{e(r['name'])} 작업 특징</h2>
      <p>{e(r['trait'])}</p>
      <p>{e(CL.LD.NEAR_TEXT[r['near']])}</p>
      <h3>출동하는 동네</h3>
      <ul class="chips">{dong_chips}</ul>
      <h2>이 페이지에서 다루는 내용</h2>
      {kw_index(groups, lambda g: CL.region_section(r, g[0], 0)[0])}
      <h2>{e(r['name'])} 폐기물·철거 안내</h2>
      {secs}
      <h2>구청 신고 배출과 방문 수거 비교</h2>
      <div class="table-wrap"><table><thead><tr><th scope="col"></th><th scope="col">{e(CL.office(r))} 신고 배출</th><th scope="col">강산자원 방문 수거</th></tr></thead><tbody>
        <tr><th scope="row">신고·스티커</th><td>직접 신고, 수수료 납부</td><td>필요 없음</td></tr>
        <tr><th scope="row">집 밖 운반</th><td>직접</td><td>직원이 집 안에서 반출</td></tr>
        <tr><th scope="row">분해·철거</th><td>직접</td><td>현장에서 진행</td></tr>
        <tr><th scope="row">비용</th><td>품목별 수수료</td><td>사진 보고 무료 견적</td></tr>
      </tbody></table></div>
      <h2>{e(r['name'])} 자주 묻는 질문</h2>
      {faq_html(faqs, open_first=True)}
      <h2>가까운 지역</h2>
      <ul>{"".join(f'<li><a href="{x["slug"]}.html">{e(x["name"])} 폐기물·철거 안내</a></li>' for x in near)}</ul>
    </article>
    <aside class="aside">{cta_card()}</aside>
  </div>
</section>"""
        imgs = [f"images/pair/{c['id']}.jpg" for c in cs] + case_imgs(cs)
        all_kws = [it["kw"] for it in items]
        ld = [{"@type": "Service", "name": title, "serviceType": "폐기물 수집·운반, 대형폐기물 수거, 철거",
               "provider": {"@id": url("index.html") + "#business"},
               "areaServed": {"@type": "AdministrativeArea", "name": r["name"], "containsPlace": [{"@type": "Place", "name": d} for d in r["dongs"]]},
               "keywords": ", ".join(all_kws), "image": [url(x) for x in imgs[:6]]}, faq_ld(faqs)]
        page(p, title, f"{r['name']} 대형폐기물·폐가구·폐가전 수거, 폐기물 처리, 철거. {', '.join(r['dongs'][:3])} 등 출동, 30년 경력 강산자원 무료 견적.",
             main, head(title, f"{', '.join(r['dongs'][:5])} 등 {r['name']} 전 지역 출동", "지역별 안내"),
             crumbs=[("local/index.html", "지역별 안내"), (p, r["name"])], ld=ld,
             og_photo=case_photo(cs[0]["id"]), og_sub=f"{r['name']} 전 지역 출동 · 사진 무료 견적", images=imgs)


def build_misc():
    p = "faq.html"
    all_faqs = list(C.GENERAL_FAQS)
    svc_faqs = ""
    for s in SERVICES:
        fq = s["faqs"] + s["more_faqs"]
        all_faqs += fq
        svc_faqs += f'<h2 style="margin-top:40px">{e(s["name"])}</h2>' + faq_html(fq)
    page(p, "자주 묻는 질문", "강산자원 폐기물 처리 자주 묻는 질문: 비용과 견적, 출동 지역, 당일·주말 작업, 소량 수거, 쓰레기집 정리, 철거·원상복구, 유품정리, 처리 불가 품목.",
         f'<section class="section"><div class="wrap"><div class="section-head"><h2>일반 문의</h2></div>{faq_html(C.GENERAL_FAQS, open_first=True)}{svc_faqs}</div></section>',
         head("자주 묻는 질문", f"견적, 일정, 작업 범위에 대해 가장 많이 받는 질문 {len(all_faqs)}개입니다."),
         crumbs=[(p, "자주 묻는 질문")], ld=[faq_ld(all_faqs)], og_sub=f"견적·일정·작업 범위 질문 {len(all_faqs)}개")

    p = "reviews.html"
    reviews = "".join(f'<blockquote class="review"><p>{e(t)}</p><footer>당근 동네업체 후기 · {e(k)}</footer></blockquote>' for k, t in C.REVIEWS)
    page(p, "고객 후기", "강산자원 고객 후기. 부모님 댁 장롱 정리, 이사 짐 정리, 가구 방문수거, 유품정리, 사무실 창고 정리를 맡긴 고객들이 남긴 후기.",
         f"""<section class="section"><div class="wrap"><div class="prose" style="margin-bottom:24px"><p>당근 동네업체에 고객이 남긴 후기 중 일부를 옮겼습니다.</p></div><div class="reviews">{reviews}</div>
<div class="btn-row" style="margin-top:28px"><a class="btn btn-ghost" href="{B['daangn']}" target="_blank" rel="noopener">당근에서 후기 더 보기</a><a class="btn btn-ghost" href="{B['naver_place']}" target="_blank" rel="noopener">네이버 플레이스 리뷰 보기</a></div></div></section>""",
         head("고객 후기", "강산자원에 작업을 맡긴 고객분들이 남겨주신 이야기입니다."), crumbs=[(p, "고객 후기")], og_sub="당근·네이버 플레이스 고객 후기")

    p = "contact.html"
    rows = [("대표전화", B["phone"]), ("카카오톡", "카카오톡 채널 ‘강산자원’ (사진 보내기 가능)"), ("주소", f"{B['address']} ({B['address_jibun']})"),
            ("가까운 역", "증산역 (6호선·경의중앙선)"), ("상담 시간", B["hours"]), ("작업", B["work_policy"]), ("출동 지역", B["area"])]
    page(p, "연락처·오시는 길", "강산자원 대표전화 010-6338-4016, 카카오톡 채널 ‘강산자원’. 서울 은평구 증산로5길 14 (증산역 인근). 24시간 상담, 연중무휴.",
         f"""<section class="section"><div class="wrap split"><div class="prose">{sheet(rows, title="연락처", sub="24시간 상담")}
  <h2>오시는 길</h2><p>강산자원 본사는 서울 은평구 증산로5길 14에 있습니다. 6호선·경의중앙선 증산역에서 가깝습니다. 작업은 고객 현장으로 직접 방문해 진행하므로, 상담과 견적은 전화나 카카오톡으로 받으시면 됩니다.</p>
  <div class="btn-row"><a class="btn btn-ghost" href="{B['naver_place']}" target="_blank" rel="noopener">네이버 지도에서 보기</a></div></div>
<aside class="aside">{cta_card()}</aside></div></section>""",
         head("연락처·오시는 길", "전화나 카카오톡으로 사진을 보내주시면 바로 견적을 드립니다."), crumbs=[(p, "연락처")],
         ld=[{"@type": "ContactPage", "name": "강산자원 연락처", "url": url(p)}], og_sub="010-6338-4016 · 카카오톡 ‘강산자원’")


# ---------------------------------------------------------------- 텍스트 파일
def build_text_files():
    with open(os.path.join(DIST, "robots.txt"), "w", encoding="utf-8") as f:
        f.write("User-agent: *\nAllow: /\n\n# 검색엔진과 AI 크롤러 모두 허용\n"
                + "".join(f"User-agent: {b}\nAllow: /\n\n" for b in ("Yeti", "Googlebot", "Googlebot-Image", "Bingbot", "GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-SearchBot", "PerplexityBot", "Google-Extended"))
                + f"Sitemap: {url('sitemap.xml')}\n")
    sm = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">']
    for path, _, _, imgs, idx in PAGES:
        if not idx:
            continue
        pr = "1.0" if path == "index.html" else "0.8" if path.startswith(("services/", "items/", "cases/", "estimate", "local/", "column/")) else "0.6"
        im = "".join(f"<image:image><image:loc>{url(i)}</image:loc></image:image>" for i in imgs[:50])
        sm.append(f"  <url><loc>{url(path)}</loc><lastmod>{TODAY}</lastmod><priority>{pr}</priority>{im}</url>")
    sm.append("</urlset>")
    open(os.path.join(DIST, "sitemap.xml"), "w", encoding="utf-8").write("\n".join(sm) + "\n")

    # 네이버 서치어드바이저 RSS 제출용: 서비스·품목·가이드·사례 분류 페이지
    feed = [(pth, t, d) for pth, t, d, _, idx in PAGES if idx and pth.startswith(("services/", "items/", "guide/", "cases/", "column/", "local/")) and not pth.endswith("index.html")]
    items = "".join(f"<item><title>{e(t)}</title><link>{url(pth)}</link><guid>{url(pth)}</guid><description>{e(d)}</description><pubDate>{RFC_DATE}</pubDate></item>" for pth, t, d in feed)
    open(os.path.join(DIST, "rss.xml"), "w", encoding="utf-8").write(
        f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>강산자원</title><link>{url("index.html")}</link>'
        f'<description>30년 경력 폐기물 처리·쓰레기집 정리·실내철거 강산자원</description><language>ko</language>{items}</channel></rss>\n')

    facts = "\n".join(f"- {k}: {v}" for k, v in C.FACTS)
    links = lambda pre: "\n".join(f"- [{t}]({url(pth)}): {d}" for pth, t, d, _, idx in PAGES if pth.startswith(pre) and idx)
    llms = f"""# 강산자원

> 강산자원은 서울 은평구 증산동에 본사를 둔 30년 경력 폐기물 처리·실내철거 전문업체입니다. 서울·경기·인천 수도권 전 지역에서 대형폐기물·폐가구·폐가전 수거, 이사 폐기물, 유품정리, 쓰레기집 정리·청소, 사무실·상가 원상복구, 실내철거를 합니다. 대표전화 010-6338-4016, 카카오톡 채널 ‘강산자원’에서 사진을 보내면 무료로 견적을 받을 수 있습니다.

## 핵심 정보
{facts}

## 서비스
{links("services/")}

## 품목별 수거
{links("items/")}

## 작업사례
{links("cases/")}

## 안내
- [무료견적·작업 절차]({url("estimate.html")})
- [현장 영상]({url("videos.html")})
- [강산 일상 (블로그 연동)]({url("daily/index.html")})
- [고객 후기]({url("reviews.html")})
- [자주 묻는 질문]({url("faq.html")})
- [회사소개]({url("about.html")})
- [연락처·오시는 길]({url("contact.html")})

## 출동 지역
{links("areas/")}

## 지역별 폐기물·철거 안내
{links("local/")}

## 폐기물 칼럼
{links("column/")}

## 폐기물 처리 가이드
{links("guide/")}

## Optional
- [전체 텍스트]({url("llms-full.txt")}): 이 사이트의 모든 안내 문구를 한 파일로 모은 것
"""
    open(os.path.join(DIST, "llms.txt"), "w", encoding="utf-8").write(llms)
    out = [llms, "\n---\n# 서비스 상세\n"]
    for s in SERVICES:
        out.append(f"\n## {s['name']}\n{s['short']}\n\n" + "\n\n".join(s["intro"]) + "\n\n처리 품목: " + ", ".join(s["items"]) + "\n이럴 때: " + " / ".join(s["situations"]))
        out.append("\n" + "\n".join(f"- {t}: {d}" for t, d in s["notes"]))
        if s.get("approach"):
            out.append("\n진행 방식: " + " → ".join(f"{t}({d})" for t, d in s["approach"]))
        out.append("\n" + "\n".join(f"Q. {q}\nA. {a}" for q, a in s["faqs"] + s["more_faqs"]) + "\n")
    out.append("\n---\n# 품목별 수거\n" + "\n".join(f"\n## {i['name']}\n{i['sub']}\n" + " ".join(i["intro"]) + "\n" + "\n".join(f"- {x}" for x in i["points"]) for i in ITEMS))
    out.append("\n\n# 작업 절차\n" + "\n".join(f"{i + 1}. {t}: {d}" for i, (t, d) in enumerate(C.PROCESS)))
    out.append("\n\n# 비용 기준 (사진 무료 견적)\n" + "\n".join(f"- {t}: {d}" for t, d in C.PRICE_FACTORS))
    out.append("\n\n# 보유 차량\n" + "\n".join(f"- {v['name']}: {v['use']}. {v['note']}" for v in C.VEHICLES))
    out.append("\n\n# 출동 지역\n" + "\n".join(f"- {a['full']}: {', '.join(a['districts'])}" for a in C.AREAS.values()))
    out.append("\n\n# 작업사례\n" + "\n".join(f"- [{CAT_NAME[c['cat']]}] {c['title']}: {c['desc']}" for c in CASES))
    out.append("\n\n# 자주 묻는 질문\n" + "\n".join(f"Q. {q}\nA. {a}" for q, a in C.GENERAL_FAQS))
    out.append("\n\n# 고객 후기 (당근 동네업체)\n" + "\n".join(f"- {k}: {t}" for k, t in C.REVIEWS))
    if INSTA:
        out.append("\n\n# 현장 영상 (인스타그램)\n" + "\n".join(f"- {v['date']} {insta_title(v)} ({v['url']})" for v in INSTA))
    if BLOG:
        out.append("\n\n# 강산 일상 (블로그)\n" + "\n".join(f"- {x['date']} {x['title']} ({x['url']})" for x in BLOG))
    for g in GUIDES:
        out.append(f"\n\n# 가이드: {g['title']}\n{g['desc']}\n" + "\n".join(f"\n## {h}\n" + "\n".join(ps) for h, ps in g["sections"]))
    open(os.path.join(DIST, "llms-full.txt"), "w", encoding="utf-8").write("".join(out) + "\n")


def copy_static():
    shutil.copytree(os.path.join(SRC, "assets"), os.path.join(DIST, "assets"))
    shutil.copytree(os.path.join(SRC, "images"), os.path.join(DIST, "images"))
    shutil.copy(os.path.join(SRC, "favicon.svg"), os.path.join(DIST, "favicon.svg"))
    static = os.path.join(SRC, "static")  # 소유확인용 HTML 파일 등은 static/ 에 두면 사이트 맨 위에 그대로 올라간다
    if os.path.isdir(static):
        for name in (n for n in os.listdir(static) if not n.startswith(".")):
            shutil.copy(os.path.join(static, name), os.path.join(DIST, name))
    # 블로그·인스타 이미지는 지금 목록에 있는 것만 복사
    os.makedirs(os.path.join(DIST, "images", "daily"), exist_ok=True)
    for x in BLOG:
        for b in x["blocks"]:
            if b["t"] == "img":
                shutil.copy(os.path.join(DATA, "blog_img", b["src"]), os.path.join(DIST, "images", "daily", b["src"]))
    os.makedirs(os.path.join(DIST, "images", "insta"), exist_ok=True)
    for v in INSTA:
        shutil.copy(os.path.join(DATA, "insta_img", v["code"] + ".jpg"), os.path.join(DIST, "images", "insta", v["code"] + ".jpg"))


if __name__ == "__main__":
    if "--offline" not in sys.argv:
        import sync
        os.makedirs(DATA, exist_ok=True)
        sync.sync_blog()
        sync.sync_instagram()
    BLOG = load_json("blog.json")
    for x in BLOG:  # 요약은 목차를 건너뛴 첫 본문 문단으로
        paras = [b["text"] for b in x["blocks"] if b["t"] == "p" and len(b["text"]) > 40 and not re.match(r"^\d+\.", b["text"])]
        if paras:
            x["summary"] = " ".join(paras)[:180]
    INSTA, seen = [], set()
    for v in sorted(load_json("instagram.json"), key=lambda v: not v["video"]):  # 같은 내용이면 영상 우선
        key = insta_title(v)
        if key not in seen and os.path.exists(os.path.join(DATA, "insta_img", v["code"] + ".jpg")):
            seen.add(key); INSTA.append(v)
    INSTA.sort(key=lambda v: v["date"], reverse=True)
    if os.path.exists(DIST):
        shutil.rmtree(DIST)
    os.makedirs(DIST)
    copy_static()
    make_pair_images()
    REGION_KWS, TOPIC_KWS = CL.assign()
    build_home()
    build_services()
    build_items()
    build_cases()
    build_videos()
    build_daily()
    build_estimate()
    build_about()
    build_areas()
    build_guides()
    build_misc()
    build_columns(TOPIC_KWS)
    build_locals(REGION_KWS)
    build_text_files()
    n_idx = sum(1 for p in PAGES if p[4])
    print(f"{len(PAGES)} pages ({n_idx} indexable, {len(CASES)} cases, {len(BLOG)} blog posts, {len(INSTA)} instagram) -> {DIST}")
