# 문의 측정과 검색 도구 설정 (내부용)

## 1. 현재 상태 (2026-10-21 확인)

- GA4·GTM·네이버 애널리틱스: **설치되어 있지 않음** (`src/content.py` `ANALYTICS` 값이 비어 있음, 페이지에 스크립트 없음)
- 클릭 측정 코드: `src/assets/site.js` 에 구현 완료. 측정 ID가 들어가면 바로 GA4로 전송됨
- 측정 ID를 넣기 전에는 이벤트가 브라우저의 `dataLayer` 에만 쌓이고 어디에도 전송되지 않음

## 2. 측정 ID 넣는 법

1. analytics.google.com → 관리 → 데이터 스트림 → 웹 → `https://gangsanjawon.com` → 측정 ID(`G-`로 시작) 복사
2. `src/content.py` 의 `ANALYTICS = {"ga4": "G-여기에", ...}` 에 넣고 커밋·푸시
3. GA4 → 관리 → 맞춤 정의 → 맞춤 측정기준 만들기 (이벤트 범위): `button_location`, `content_group`, `content_topic`
4. 실시간 보고서에서 전화·카톡 버튼을 눌러 `click_call` / `click_kakao` 가 1번씩 들어오는지 확인

## 3. 이벤트 정의

| 이벤트 | 언제 | 함께 보내는 값 |
|---|---|---|
| `click_call` | `tel:` 링크 클릭 | `page_path`, `button_location`(상단·본문·하단·고정), `content_group`(home·service·item·case·column·region·process 등), `content_topic`(페이지 slug) |
| `click_kakao` | 카카오톡 채널·채팅 링크 클릭 | 위와 같음 |

- 전화번호, 이름, 주소, 상담 내용, 사진은 보내지 않습니다.
- 문서 전체에 리스너 하나만 있어 한 번 클릭에 한 번만 기록됩니다. `preventDefault` 를 쓰지 않아 전화·카톡 이동을 막지 않습니다.
- **클릭은 통화·상담·예약이 아닙니다.** 보고서에서 ‘문의 클릭’으로만 읽어 주세요.

## 4. 실제 상담·예약 (qualified_lead, booking_confirmed)

전화와 카카오톡 상담은 홈페이지 밖에서 일어나므로 자동으로 알 수 없습니다. 아래 수동 기록이 가장 현실적입니다.

1. 상담 기록표(구글 시트 등)에 한 줄씩 기록: 날짜, 경로(전화/카톡), **어떻게 알고 연락했는지**(홈페이지·네이버·당근·블로그·지인), 상담 품목, 견적 여부, 예약 확정 여부, 작업일
2. 기준
   - `qualified_lead`: 사진이나 품목·지역을 받아 견적을 낼 수 있는 상담
   - `booking_confirmed`: 날짜를 잡아 예약이 확정된 건
3. 매주 한 번 시트 합계와 GA4 `click_call`/`click_kakao` 수를 나란히 비교
4. 연동을 원하면: GA4 측정 프로토콜(Measurement Protocol)로 시트 행을 이벤트로 보내는 방법이 있지만, API 비밀키와 클릭–상담을 잇는 식별값이 필요하고 개인정보를 보내지 않도록 설계해야 합니다. 상담량이 적을 때는 수동 기록을 권장합니다.

## 5. 검색 도구에서 할 일

**네이버 서치어드바이저** (searchadvisor.naver.com)
1. 웹마스터 도구 → gangsanjawon.com → 요청 → 사이트맵 제출: `https://gangsanjawon.com/sitemap.xml` (이미 제출했다면 다시 제출 불필요)
2. 요청 → RSS 제출: `https://gangsanjawon.com/rss.xml`
3. 요청 → 웹 페이지 수집: 새 상세 사례 5개와 `local/mapo.html`, `column/sofa.html`, `items/sofa.html`, `estimate.html` 주소를 하나씩 수집 요청
4. 리포트 → 사이트 진단 / 검색 노출에서 색인 상태 확인

**구글 서치콘솔** (search.google.com/search-console)
1. Sitemaps → `sitemap.xml` 상태가 ‘성공’인지 확인 (다시 제출해도 됨)
2. URL 검사 → 위 주소들을 넣고 ‘색인 생성 요청’
3. 페이지(색인 생성) 보고서에서 ‘제외됨’ 사유 확인. `daily/` 글은 블로그 원문을 canonical로 지정한 noindex 페이지라 제외되는 것이 정상

## 6. canonical·사이트맵 정책

| 페이지 | 색인 | canonical | 사이트맵 |
|---|---|---|---|
| 일반 페이지 160개 (상세 사례 포함) | index | 자기 주소 | 포함, lastmod = 내용이 실제로 바뀐 날 |
| `daily/` 블로그 재게시 9개 | noindex,follow | 블로그 원문 | 제외 |

lastmod는 `src/data/lastmod.json` 에 페이지별 내용 해시와 날짜로 저장합니다. 내용이 같으면 날짜가 바뀌지 않습니다.
