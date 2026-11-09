# -*- coding: utf-8 -*-
"""블로그 글에서 작업 전·후 사진 쌍을 자동으로 찾아 작업사례 카드로 만든다.

블로그 동기화(sync.py) 뒤 build.py 가 호출한다. 새 글이 올라오면 다음 자동 업데이트 때 사례가 늘어난다.

찾는 형식
  1) 좌우로 붙인 사진 + '왼쪽 사진 / 수거 전 | 설명 / 오른쪽 사진 / 수거 후 | 설명'
  2) 사진 한 장씩 + '수거 전 | 설명' 다음 사진 + '수거 후 | 설명'
쓰지 않는 사진
  - 라벨에 '예상', '참고', '원본', '중', '과정'이 들어간 사진 (가공·참고·작업 중 사진)
  - 글자를 넣은 대표 이미지(라벨이 없는 사진)
지역
  - 자동으로 지역을 붙이지 않는다. 같은 사진이 다른 지역 이름의 글에 다시 쓰이는 경우가 있어서,
    지역 페이지에는 사람이 확인한 사례(case_data.py, content_more.CASE_REGION)만 연결한다.
  - 글 제목의 지역명은 참고용(title_region)으로만 남긴다.
중복
  - 다른 글이나 이미 쓰는 사진과 거의 같은 사진(잘라낸 것 포함)은 건너뛴다 (photo_dups).
"""
import re

import local_data as LD

BEFORE = re.compile(r"^(수거|정리|작업|철거) 전$")
AFTER = re.compile(r"^(실제 )?(수거|정리|작업|철거|프레임 수거) 후$")
BAD = ("예상", "참고", "원본")
NO_REGION = ("촬영지", "지역별 안내", "지역 안내를 위한", "지역 독자를 위한", "안내용 사례")
# 이미 손으로 정리한 사례(k01~k05)와 같은 글은 건너뛴다
SKIP_POSTS = {"224444069357", "224444047796", "224444905249"}

CAT_RULES = [
    ("estate", ("유품",)), ("trash", ("쓰레기",)),
    ("office", ("사무실", "사무용", "파티션", "학원", "책상수거")),
    ("demolition", ("철거", "인테리어", "공사폐기물", "공사 폐기물")),
    ("outdoor", ("화분", "옥상", "지하창고", "창고", "놀이기구", "베란다")),
    ("moving", ("이사", "이삿짐")),
]
SERVICE = {"estate": "estate", "trash": "trash-house", "office": "office", "demolition": "demolition",
           "outdoor": "outdoor", "moving": "moving", "household": "household", "store": "store"}
ITEM_WORDS = ["놀이기구", "옷장", "장롱", "소파", "쇼파", "리클라이너", "침대", "매트리스", "식탁", "장식장", "TV", "냉장고", "가전", "주방용품", "그릇",
              "수납장", "화분", "책상", "의자", "파티션", "사무용품", "마대", "주름관", "목재", "생활용품"]


def _region(title):
    pairs = []
    for r in LD.REGIONS:
        if r["slug"] in ("seoul", "gyeonggi", "incheon"):
            continue
        pairs += [(a, r["slug"]) for a in r["aliases"]]
    pairs += list(LD.DONG_TO_REGION.items())
    for alias, slug in sorted(pairs, key=lambda p: -len(p[0])):
        if alias in title:
            return slug
    return None


def _tokens(blocks):
    out = []
    for b in blocks:
        if b["t"] == "table":
            for row in b["rows"]:
                for cell in row:
                    out += [t.strip() for t in cell.split("|") if t.strip()]
        elif b.get("text"):
            out += [t.strip() for t in b["text"].split("|") if t.strip()]
    return out


def _clean(cap):
    cap = re.sub(r"\s+", " ", cap or "").strip().rstrip(" .,")
    return cap if len(cap) <= 60 else cap[:58].rstrip(" .,") + "…"


def find_pairs(post):
    """[(before_src, before_crop, before_cap, after_src, after_crop, after_cap)]"""
    bl = post["blocks"]
    pairs, pending = [], None
    for i, b in enumerate(bl):
        if b["t"] != "img":
            continue
        after_blocks = []
        for c in bl[i + 1:i + 8]:
            if c["t"] == "img":
                break
            after_blocks.append(c)
        tok = _tokens(after_blocks)
        if not tok:
            pending = None
            continue
        if tok[0] == "왼쪽 사진" and "오른쪽 사진" in tok:
            k = tok.index("오른쪽 사진")
            left, right = tok[1:k], tok[k + 1:k + 3]
            lab_l, cap_l = (left + ["", ""])[:2]
            lab_r, cap_r = (right + ["", ""])[:2]
            if BEFORE.match(lab_l) and AFTER.match(lab_r) and not any(w in lab_l + lab_r for w in BAD):
                pairs.append((b["src"], "L", _clean(cap_l), b["src"], "R", _clean(cap_r)))
            pending = None
            continue
        lab, cap = (tok + [""])[:2]
        if any(w in lab for w in BAD):
            pending = None
        elif BEFORE.match(lab):
            pending = (b["src"], None, _clean(cap))
        elif AFTER.match(lab) and pending:
            pairs.append(pending + (b["src"], None, _clean(cap)))
            pending = None
    return pairs


def extract(blog, is_dup=lambda src, post_id: False):
    """블로그 글 목록 → 자동 사례 목록 (최신 글 먼저). is_dup(사진, 글 id)가 참이면 그 쌍은 건너뛴다."""
    out = []
    for post in blog:
        if post["id"] in SKIP_POSTS:
            continue
        pairs = [p for p in find_pairs(post) if not (is_dup(p[0], post["id"]) or is_dup(p[3], post["id"]))]
        if not pairs:
            continue
        title = post["title"]
        body = " ".join(b.get("text", "") for b in post["blocks"])
        title_region = None if any(w in body for w in NO_REGION) else _region(title)
        region = None
        cat = next((c for c, words in CAT_RULES if any(w in title for w in words)), "household")
        items = [w for w in ITEM_WORDS if w in title][:3]
        rname = ""
        what = "·".join(items) + " 정리" if items else {"estate": "유품정리", "office": "사무실 정리", "demolition": "공사 잔재 정리"}.get(cat, "현장 정리")
        base = (rname + " " if rname else "") + what
        for n, (bs, bc, bcap, as_, ac, acap) in enumerate(pairs):
            out.append(dict(
                id=f"a{post['id']}{n + 1}", title=base + (f" ({n + 1})" if len(pairs) > 1 else ""),
                cat=cat, service=SERVICE[cat], region=region, title_region=title_region, post=post["id"], date=post["date"], url=post["url"],
                desc=(f"작업 전: {bcap}. " if bcap else "") + (f"작업 후: {acap}." if acap else ""),
                before=(bs, bc), after=(as_, ac)))
    return out
