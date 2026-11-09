# -*- coding: utf-8 -*-
"""블로그 사진 중복 찾기: 같은 사진을 잘라 내거나 크기를 바꿔 다른 글에 다시 쓴 경우를 찾는다.

색 분포가 비슷한 사진만 골라(빠른 1차), 축소한 흑백 사진을 여러 배율·위치로 맞대어 상관계수를 본다(2차).
결과는 data/photo_dups.json 에 저장해 다음 빌드 때 다시 계산하지 않는다.
"""
import json
import os

import numpy as np
from PIL import Image

HIST_MIN = 0.62   # 1차: 색 분포 겹침
NCC_MIN = 0.66    # 2차: 형태 일치


def _hist(path):
    a = np.asarray(Image.open(path).convert("RGB").resize((96, 128))) // 32
    idx = a[..., 0].astype(int) * 64 + a[..., 1] * 8 + a[..., 2]
    h = np.bincount(idx.ravel(), minlength=512).astype(float)
    return h / h.sum()


def _ncc(a, b):
    a = a - a.mean(); b = b - b.mean()
    d = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / d) if d else 0.0


def _match(pa, pb):
    A = Image.open(pa).convert("L"); B = Image.open(pb).convert("L")
    best = -1.0
    for X, Y in ((A, B), (B, A)):
        t = np.asarray(X.resize((48, max(1, int(48 * X.height / X.width)))), dtype=float)
        th, tw = t.shape
        for s in np.arange(0.6, 1.01, 0.05):
            W = int(48 / s); H = int(W * Y.height / Y.width)
            if th > H or tw > W:
                continue
            yy = np.asarray(Y.resize((W, H)), dtype=float)
            for oy in range(0, H - th + 1, 2):
                for ox in range(0, W - tw + 1, 2):
                    best = max(best, _ncc(t, yy[oy:oy + th, ox:ox + tw]))
    return best


def find(images, cache_path):
    """images: {사진 파일명: (글 id, 경로)} → {사진: [같은 사진으로 보이는 다른 글의 사진, ...]}"""
    cache = json.load(open(cache_path, encoding="utf-8")) if os.path.exists(cache_path) else {}
    names = sorted(images)
    if cache.get("_names") == names:
        return cache["dups"]
    hists = {n: _hist(images[n][1]) for n in names}
    pairs_done = cache.get("pairs", {})
    dups = {n: [] for n in names}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if images[a][0] == images[b][0]:
                continue
            key = a + "|" + b
            if key not in pairs_done:
                same = False
                if np.minimum(hists[a], hists[b]).sum() >= HIST_MIN:
                    same = _match(images[a][1], images[b][1]) >= NCC_MIN
                pairs_done[key] = same
            if pairs_done[key]:
                dups[a].append(b); dups[b].append(a)
    json.dump({"_names": names, "dups": dups, "pairs": pairs_done}, open(cache_path, "w", encoding="utf-8"), ensure_ascii=False)
    return dups
