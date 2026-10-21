# -*- coding: utf-8 -*-
"""지역 칼럼·주제 칼럼의 키워드 분류와 소제목 문단 생성.

키워드마다 소제목 하나와 짧은 문단을 만든다. 문단은 키워드 종류(버리기·수거·비용·철거·업체·신고 등)와
지역/주제 고유 정보를 조합해, 같은 페이지 안에서도 문장이 겹치지 않도록 여러 문형 중 하나를 고른다.
"""
import hashlib
from collections import OrderedDict

import column_data as CD
import keywords as KW
import local_data as LD


def _h(s, n):
    return int(hashlib.md5(s.encode("utf-8")).hexdigest(), 16) % n


def has_batchim(word):
    for ch in reversed(word.strip()):
        if "가" <= ch <= "힣":
            return (ord(ch) - 0xAC00) % 28 != 0
        if ch.isalnum():
            return ch.lower() in "lmnr0136789"
    return False


def josa(word, pair):
    a, b = pair.split("/")
    return word + (a if has_batchim(word) else b)


# ---------------------------------------------------------------- 분류
_ALIASES = sorted([(a, r["slug"], None) for r in LD.REGIONS for a in r["aliases"]] +
                  [(d, s, d) for d, s in LD.DONG_TO_REGION.items()], key=lambda x: -len(x[0]))
REGION = OrderedDict((r["slug"], r) for r in LD.REGIONS)
TOPIC = OrderedDict((t["slug"], t) for t in CD.TOPICS)


def classify_region(w):
    for a, slug, dong in _ALIASES:
        if w.startswith(a) and len(w) > len(a):
            return slug, dong, a, w[len(a):]
    return None


def classify_topic(w):
    for slug, subs in CD.RULES:
        if any(s in w for s in subs):
            return slug
    return None


def assign():
    """모든 키워드를 지역 페이지 또는 주제 페이지에 배정한다."""
    regions = OrderedDict((s, []) for s in REGION)
    topics = OrderedDict((s, []) for s in TOPIC)
    for w in KW.region_keywords() + KW.topic_keywords():
        r = classify_region(w)
        if r:
            if w not in [x["kw"] for x in regions[r[0]]]:
                regions[r[0]].append(dict(kw=w, dong=r[1], alias=r[2], rest=r[3]))
            continue
        t = classify_topic(w)
        if t and w not in topics[t]:
            topics[t].append(w)
    return regions, topics


# ---------------------------------------------------------------- 주제 칼럼 문단
SUFFIXES = [
    ("버려주는업체", "company", "버려주는 업체"), ("버리는방법", "throw", "버리는 방법"), ("버리는비용", "cost", "버리는 비용"),
    ("버리는업체", "company", "버리는 업체"), ("버리는법", "throw", "버리는 법"), ("버리기", "throw", "버리기"),
    ("수거업체비용", "cost", "수거 업체 비용"), ("수거업체", "company", "수거 업체"), ("수거비용", "cost", "수거 비용"), ("수거가격", "cost", "수거 가격"),
    ("방문수거", "collect", "방문 수거"), ("무상수거", "free", "무상 수거"), ("수거", "collect", "수거"),
    ("처리업체비용", "cost", "처리 업체 비용"), ("처리전문업체", "company", "처리 전문 업체"), ("처리업체", "company", "처리 업체"),
    ("처리비용", "cost", "처리 비용"), ("처리가격", "cost", "처리 가격"), ("처리비", "cost", "처리비"), ("처리장", "process", "처리장"), ("처리", "process", "처리"),
    ("철거공사비용", "dcost", "철거 공사 비용"), ("철거공사견적", "dcost", "철거 공사 견적"), ("철거공사비", "dcost", "철거 공사비"), ("철거공사", "demo", "철거 공사"),
    ("철거업체", "company", "철거 업체"), ("철거비용", "dcost", "철거 비용"), ("철거비", "dcost", "철거비"), ("철거", "demo", "철거"),
    ("폐기업체", "company", "폐기 업체"), ("폐기비용", "cost", "폐기 비용"), ("폐기가격", "cost", "폐기 가격"), ("폐기물", "waste", "폐기물"), ("폐기", "throw", "폐기"),
    ("청소업체", "company", "청소 업체"), ("청소비용", "cost", "청소 비용"), ("청소", "clean", "청소"),
    ("정리업체비용", "cost", "정리 업체 비용"), ("정리업체", "company", "정리 업체"), ("정리비용", "cost", "정리 비용"), ("정리사", "company", "정리사"), ("정리", "organize", "정리"),
    ("소각업체", "process", "소각 업체"), ("소각장", "process", "소각장"), ("소각", "process", "소각"),
    ("수집운반업체", "company", "수집·운반 업체"), ("수집운반업", "company", "수집·운반업"), ("수집운반", "process", "수집·운반"),
    ("운반업체", "company", "운반 업체"), ("운반차량", "process", "운반 차량"), ("운반차", "process", "운반 차량"),
    ("업체비용", "cost", "업체 비용"), ("업체순위", "company", "업체 고르는 법"), ("업체", "company", "업체"),
    ("비용", "cost", "비용"), ("가격", "cost", "가격"), ("견적", "dcost", "견적"),
    ("처분", "throw", "처분"), ("제거", "demo", "제거"), ("분해", "demo", "분해"), ("배출", "throw", "배출"), ("빼기", "throw", "빼기"),
    ("스티커", "sticker", "스티커"), ("옮기기", "move", "옮기기"), ("절차", "process", "절차"), ("문의", "company", "문의"),
    ("전문", "company", "전문"), ("시공", "demo", "시공"), ("작업", "demo", "작업"), ("복구", "demo", "복구"), ("공사", "demo", "공사"),
]


def split_kw(kw, topic_noun):
    for suf, kind, label in SUFFIXES:
        if kw.endswith(suf) and len(kw) > len(suf):
            noun = kw[: -len(suf)]
            return noun, kind, label
    return kw, "plain", ""


def pretty(noun):
    """'침대매트리스' 같은 붙여 쓴 말을 그대로 두되, 흔한 결합어는 띄어 쓴다."""
    for a, b in (("침대매트리스", "침대 매트리스"), ("김치냉장고", "김치냉장고"), ("사무실", "사무실 "), ("아파트", "아파트 "), ("상가", "상가 "),
                 ("원룸", "원룸 "), ("가정집", "가정집 "), ("대형", "대형 "), ("중고", "중고 "), ("폐", "폐")):
        if noun.startswith(a) and len(noun) > len(a) and b.endswith(" "):
            return (b + noun[len(a):]).replace("  ", " ")
    return noun


TPL = {
    "throw": [
        "{Neul} 버리는 방법은 크게 두 가지입니다. {gov} 직접 옮기기 어렵거나 양이 많다면 강산자원이 집 안에서 꺼내 한 번에 처리합니다.",
        "{Neul} 버리려면 먼저 직접 배출할지, 방문 수거를 맡길지 정하세요. {fact} 강산자원에 맡기시면 분해와 운반까지 모두 맡습니다.",
        "{N} {Leun} 생각보다 손이 많이 갑니다. {care} 강산자원은 사진만 보고 필요한 인원과 차량을 정해 방문합니다.",
        "{fact} 무겁거나 계단이 좁다면 {N} {Leul} 혼자 무리하기보다 방문 수거를 알아보세요. 소량도 출동합니다.",
    ],
    "cost": [
        "{N} {Leun} 정해진 단가표보다 현장 조건에 따라 달라집니다. {cost} 사진을 보내주시면 무료로 견적을 드립니다.",
        "{cost} 그래서 강산자원은 {N} {Leul} 사진으로 먼저 확인한 뒤 안내합니다. 사진에 없던 짐이 추가되면 작업 전에 다시 알려드립니다.",
        "{N} {L}{eul2} 줄이려면 버릴 물건을 한 번에 모아 맡기는 것이 좋습니다. 여러 번 나눠 부르면 출동이 늘어납니다. {cost}",
    ],
    "company": [
        "{N} {Leul} 고를 때는 사진으로 견적을 주는지, 견적에 포함되는 범위를 알려주는지, 적법하게 처리하는지 확인하세요.",
        "강산자원의 {N} 상담에서는 {p0}, {p1}까지 함께 안내합니다.",
        "{N} {Leul} 찾을 때 가장 많이 듣는 걱정은 현장에서 비용이 달라지는 것입니다. 강산자원은 사진으로 범위를 정하고, 달라질 일이 있으면 작업 전에 먼저 안내합니다.",
    ],
    "collect": [
        "강산자원은 서울·경기·인천에서 {N} {Leul} 합니다. 주요 작업은 {p0}, {p1}입니다.",
        "{N} {Leun} 집 안에서 꺼내는 일부터 시작합니다. {fact}",
        "{N} {Leul} 맡기실 때는 품목 사진과 층수, 엘리베이터 유무만 알려주세요. 날짜를 정해 약속한 시간에 방문합니다.",
    ],
    "free": [
        "{N} 무상 수거는 가전만 단독으로 버릴 때 이용할 수 있습니다. {gov} 가구나 잔짐이 함께 있거나 날짜가 정해져 있다면 강산자원 방문 수거가 편합니다.",
    ],
    "process": [
        "{N} {Leun} 종류에 맞는 경로로 진행해야 합니다. {gov} 강산자원은 수거한 폐기물을 성상별로 나눠 처리합니다.",
        "{N} {L}에서 중요한 것은 처리 과정이 분명한지입니다. {care}",
        "{fact} 강산자원은 {N} {Leul} 수거부터 처리까지 직접 진행합니다.",
    ],
    "demo": [
        "{N} {Leun} 철거와 잔재 반출을 함께 해야 다음 공정이 늦어지지 않습니다. 강산자원은 {p0}부터 {p1}까지 한 팀이 진행합니다.",
        "{N} {L} 전에는 남길 부분과 철거할 부분을 사진에 표시해 보내주세요. {care}",
        "{fact} 강산자원은 {N} {L} 후 바닥 잔재까지 정리합니다.",
    ],
    "dcost": [
        "{N} {Leun} 면적만으로 정해지지 않습니다. {cost} 견적서에 잔재 처리비가 포함되어 있는지 꼭 확인하세요.",
        "{cost} 강산자원은 {N} {Leul} 현장 사진으로 범위를 확인한 뒤 안내합니다.",
    ],
    "waste": [
        "{N} 폐기물은 양과 종류에 따라 배출 방법이 다릅니다. {gov} 많거나 무겁다면 강산자원이 방문해 처리합니다.",
        "{N} 폐기물이 많이 나왔다면 분류하지 않은 그대로 두셔도 됩니다. 강산자원이 현장에서 나눠 반출합니다. {care}",
        "{fact} {N} 폐기물도 같은 방식으로 수거합니다.",
    ],
    "clean": [
        "{N} 청소는 쓰레기와 짐을 먼저 빼내는 일이 대부분입니다. 강산자원은 {p0}, {p1}까지 진행합니다. {care}",
        "{fact} {N} 청소가 필요하다면 방마다 사진을 찍어 보내주세요.",
    ],
    "organize": [
        "{N} 정리는 남길 물건만 정하면 나머지는 강산자원이 한 번에 반출합니다. {care}",
        "{N} 정리를 혼자 하기 어렵다면 사진을 보내주세요. 양을 보고 인원과 시간을 안내합니다.",
    ],
    "sticker": [
        "{N} 스티커는 구청(주민센터) 대형폐기물 신고 후 받는 배출 표시입니다. {gov} 업체 방문 수거를 이용하면 스티커가 필요 없습니다.",
    ],
    "move": [
        "{Neul} 무리해서 옮기면 다치기 쉽습니다. 무겁거나 계단이 좁다면 사진으로 반출 경로를 먼저 확인합니다.",
    ],
    "plain": [
        "{N} 작업은 현장마다 조건이 달라 사진으로 먼저 확인합니다. 주요 작업은 {p0}, {p1}입니다.",
        "{Neun} 현장마다 조건이 달라 사진으로 먼저 확인합니다. {cost}",
        "{fact} {N} 관련 문의도 사진 한 장이면 상담이 시작됩니다.",
    ],
}


def _sentences(text):
    return [x.strip().rstrip(".") + "." for x in text.replace("다. ", "다.|").split("|") if x.strip()]


def topic_section(t, kw, idx=0):
    noun, kind, label = split_kw(kw, t["noun"])
    N = pretty(noun) if noun else t["noun"]
    L = label or N
    facts = _sentences(" ".join(t["intro"]))
    tpls = TPL.get(kind, TPL["plain"])
    s = tpls[(_h(t["slug"], len(tpls)) + idx) % len(tpls)]
    text = s.format(N=N, L=L, gov=t["gov"], cost=t["cost"], care=t["care"], p0=t["points"][idx % len(t["points"])],
                    p1=t["points"][(idx + 1) % len(t["points"])], fact=facts[idx % len(facts)],
                    Neul=josa(N, "을/를"), Neun=josa(N, "은/는"), Leul=josa(L, "을/를"), Leun=josa(L, "은/는"),
                    eul2="을" if has_batchim(L) else "를")
    heading = f"{N} {label}".strip()
    return heading, text


def topic_groups(t, kws):
    """같은 소제목(명사+종류)이 되는 키워드는 한 섹션으로 묶는다."""
    groups = OrderedDict()
    for kw in kws:
        noun, kind, label = split_kw(kw, t["noun"])
        key = (pretty(noun) if noun else t["noun"], label)
        groups.setdefault(key, []).append(kw)
    return list(groups.values())


# ---------------------------------------------------------------- 지역 칼럼 문단
RTYPE = {
    "대형폐기물": "bulky", "대형폐기물수거": "bulky", "청대형폐기물": "report",
    "폐기물": "general", "폐기물처리": "general", "폐기물수거": "general", "폐기물처리장": "general",
    "폐기물업체": "company", "폐기물처리업체": "company", "폐기물수거업체": "company",
    "폐기물신고": "report", "청폐기물": "report", "청폐기물신고": "report", "청폐기물수거": "report",
    "생활폐기물": "household", "가정폐기물": "household", "가정폐기물처리": "household", "소형폐기물": "household", "쓰레기수거": "household",
    "폐가전": "appliance", "폐가전수거": "appliance", "가전수거": "appliance",
    "폐가구": "furniture", "폐가구수거": "furniture", "가구수거": "furniture", "가구폐기": "furniture", "가구버리기": "furniture",
    "침대수거": "furniture", "붙박이장철거": "demolition",
    "철거": "demolition", "철거업체": "demolition", "철거공사": "demolition", "인테리어철거": "demolition",
    "상가철거": "store", "식당철거": "store", "폐업": "store",
    "사무실": "office", "사무실철거": "office",
    "이사폐기물": "moving", "유품정리": "estate", "쓰레기집청소": "trash", "정리업체": "estate",
}

RLABEL = {
    "대형폐기물": "대형폐기물", "대형폐기물수거": "대형폐기물 수거", "청대형폐기물": "구청 대형폐기물 신고",
    "폐기물": "폐기물", "폐기물처리": "폐기물 처리", "폐기물수거": "폐기물 수거", "폐기물처리장": "폐기물 처리장",
    "폐기물업체": "폐기물 업체", "폐기물처리업체": "폐기물 처리 업체", "폐기물수거업체": "폐기물 수거 업체",
    "폐기물신고": "폐기물 신고", "청폐기물": "구청 폐기물 배출", "청폐기물신고": "구청 폐기물 신고", "청폐기물수거": "구청 폐기물 수거",
    "생활폐기물": "생활폐기물", "가정폐기물": "가정 폐기물", "가정폐기물처리": "가정 폐기물 처리", "소형폐기물": "소형 폐기물", "쓰레기수거": "쓰레기 수거",
    "폐가전": "폐가전", "폐가전수거": "폐가전 수거", "가전수거": "가전 수거",
    "폐가구": "폐가구", "폐가구수거": "폐가구 수거", "가구수거": "가구 수거", "가구폐기": "가구 폐기", "가구버리기": "가구 버리기",
    "침대수거": "침대 수거", "붙박이장철거": "붙박이장 철거",
    "철거": "철거", "철거업체": "철거 업체", "철거공사": "철거 공사", "인테리어철거": "인테리어 철거",
    "상가철거": "상가 철거", "식당철거": "식당 철거", "폐업": "폐업 정리",
    "사무실": "사무실 정리", "사무실철거": "사무실 철거",
    "이사폐기물": "이사 폐기물", "유품정리": "유품정리", "쓰레기집청소": "쓰레기집 청소", "정리업체": "정리 업체",
}

REGION_FAQ = [
    ("{R}도 당일 출동이 되나요?", "{NEAR}"),
    ("{R}에서 대형폐기물을 직접 버리려면 어떻게 하나요?", "{OFFICE} 홈페이지나 주민센터에서 배출 신고를 하고 신고필증(스티커)을 붙여 내놓는 방식입니다. 수수료와 배출 요일·시간은 지자체마다 다르니 {OFFICE} 안내를 확인하세요. 집 밖까지 옮기기 어렵다면 방문 수거 견적과 비교해 보세요."),
    ("{R}에서 가구 한두 개만 버려도 되나요?", "네. 소량도 출동합니다. 품목과 층수, 엘리베이터 유무를 사진과 함께 보내주세요."),
    ("엘리베이터가 없는 {R} 빌라도 되나요?", "네. 계단으로 옮길 수 있는지, 분해나 사다리차가 필요한지를 사진이나 현장 확인으로 판단합니다."),
]


def region_faqs(r, extra=()):
    """지역 FAQ. extra(지역 전용 질문)가 있으면 앞에 두고, 같은 주제의 공통 질문은 뺀다."""
    out = list(extra)
    for q, a in REGION_FAQ:
        if extra and "직접 버리려면" in q:
            continue
        out.append((q.format(R=r["name"]), a.format(R=r["name"], NEAR=LD.NEAR_TEXT[r["near"]], OFFICE=office(r))))
    return out


OFFICE = {"seoul": "각 구청", "gyeonggi": "각 시청·구청", "incheon": "각 구청", "jung": "중구청", "incheon-seo": "인천 서구청",
          "songdo": "연수구청", "yeongjong": "인천 중구청"}


def office(r):
    if r["slug"] in OFFICE:
        return OFFICE[r["slug"]]
    return r["name"] + "청"


def region_groups(items):
    """같은 지역(또는 동)과 같은 뜻의 키워드는 한 섹션으로 묶는다. 예: 강남구대형폐기물 + 강남대형폐기물"""
    groups = OrderedDict()
    for it in items:
        key = (it.get("dong") or "", RLABEL.get(it["rest"], it["rest"]))
        groups.setdefault(key, []).append(it)
    return list(groups.values())
