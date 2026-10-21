# 새 현장 상세 기록 한 건 추가하는 방법

CMS 없이 파일 하나만 고치면 됩니다. 사이트맵·지역 페이지·서비스 페이지·품목 페이지·칼럼 연결은 자동입니다.

1. 블로그(behalf1oj)에 현장 글을 올립니다. 3시간 안에 자동 동기화되어 `src/data/blog.json` 과 `src/data/blog_img/` 에 들어옵니다.
   (바로 반영하려면 GitHub → Actions → ‘홈페이지 자동 업데이트’ → Run workflow)
2. `src/case_data.py` 의 `DETAILS` 목록에 한 건을 추가합니다. 기존 항목을 복사해서 고치면 됩니다.
   - `slug`: 영문 주소 (예: `jongno-store-closing`) → `cases/detail/jongno-store-closing.html`
   - `region`: 지역 페이지 slug (`src/local_data.py` 의 slug, 예: `mapo`). 이 값이 맞으면 해당 지역 페이지 ④에 ‘실제 작업사례’로 자동 표시됩니다.
   - `cat`, `service`, `services`, `items`, `columns`: 연결할 분류·서비스·품목·칼럼 slug
   - `source`: 블로그 원문 주소, `date`: 원문 날짜, `updated`: 고친 날짜
   - `request`, `site`, `problems`, `process`, `scope`, `prepare`: 원문과 사진으로 확인되는 내용만. 모르는 항목은 빼거나 빈 값으로 두면 그 줄이 표시되지 않습니다.
   - `photos`: `("블로그이미지파일.jpg", None|"L"|"R", "before"|"process"|"after", "캡션")`. 좌우로 붙인 사진은 "L"/"R"로 반씩 씁니다. 글자를 넣은 대표 이미지(보통 `-1.jpg`)와 예상·합성 이미지는 넣지 않습니다.
3. 기존 전후 사진 카드와 같은 현장이면 `CARD_TO_DETAIL` 에 카드 id를 연결합니다.
4. `docs/case-sources.md` 표에 출처와 확인한 내용을 한 줄 추가합니다 (내부 메모는 공개 파일에 쓰지 않습니다).
5. 로컬 확인: `cd src && python3 build.py --offline` 후 `dist/cases/detail/<slug>.html` 확인.
6. 커밋·푸시하면 GitHub Actions가 빌드·배포합니다. 사이트맵에 새 주소가 자동으로 들어가고 lastmod는 그날 날짜가 됩니다.

쓰지 말 것: 상세 주소(번지·호수·아파트 동호수), 고객 이름·연락처, 사진으로 추정한 작업 시간·인원·비용, 확인되지 않은 수량.
