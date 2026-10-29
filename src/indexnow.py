# -*- coding: utf-8 -*-
"""오늘 내용이 바뀐 페이지 주소를 IndexNow 형식(JSON 한 줄)으로 출력한다.

GitHub Actions 가 배포를 마친 뒤 이 값을 api.indexnow.org 로 보낸다 (.github/workflows/deploy.yml).
바뀐 페이지가 없으면 아무것도 출력하지 않는다. 블로그 재게시 글(daily/)은 보내지 않는다.
"""
import json
import os
from datetime import date

import content as C

SRC = os.path.dirname(os.path.abspath(__file__))
lm = json.load(open(os.path.join(SRC, "data", "lastmod.json"), encoding="utf-8"))
today = date.today().isoformat()
host = C.SITE_URL.split("//", 1)[1].rstrip("/")
urls = [C.SITE_URL.rstrip("/") + "/" + ("" if p == "index.html" else p)
        for p, v in sorted(lm.items()) if v["date"] == today and not p.startswith("daily/")]
if urls:
    print(json.dumps({"host": host, "key": C.INDEXNOW_KEY, "keyLocation": f"{C.SITE_URL.rstrip('/')}/{C.INDEXNOW_KEY}.txt",
                      "urlList": urls[:10000]}, ensure_ascii=False, separators=(",", ":")))
