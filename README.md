# 강산자원 홈페이지

`dist/` 폴더가 완성된 홈페이지입니다. `src/build.py`가 이 폴더를 만듭니다.

## 구성

| 메뉴 | 파일 | 내용 |
|---|---|---|
| 서비스 (11) | `services/*.html` | 서비스마다 '이런 경우라면', 준비할 것, 진행 방식, 사례, FAQ |
| 품목별 수거 (12) | `items/*.html` | 장롱, 침대, 냉장고, 에어컨 등 품목별 안내와 버리는 방법 비교 |
| 작업사례 (83건) | `cases/*.html` | 전체 + 8개 분류 페이지 (이사, 유품, 쓰레기집, 가정, 사무실, 폐업, 철거, 야외) |
| 강산 일상 | `daily/*.html` | 네이버 블로그 behalf1oj 글 자동 연동 |
| 영상 | `videos.html` | 인스타그램 @gangsan_30 게시물 자동 연동 |
| 이용안내 | `estimate.html`, `areas/`, `guide/`, `faq.html`, `reviews.html` | 무료견적, 출동지역, 가이드 11편, FAQ, 후기 |
| 회사소개 | `about.html`, `contact.html` | 회사 소개, 보유 차량, 연락처 |

## 블로그·인스타 자동 업데이트

`python3 build.py`를 실행하면 `sync.py`가 먼저 돌아서

- 네이버 블로그 `behalf1oj`의 RSS로 새 글을 찾아 본문과 사진을 받아 `daily/`에 페이지를 만들고
- 인스타그램 `gangsan_30`의 최근 게시물(릴스 포함) 썸네일과 글을 받아 `videos.html`에 넣습니다.

받아온 내용은 `src/data/`에 저장됩니다. 블로그나 인스타그램 접속이 실패하면 저장본으로 만들기 때문에 홈페이지가 깨지지 않습니다.

**자동으로 돌리기:** `.github/workflows/deploy.yml`이 GitHub Actions에서 3시간마다 이 작업을 하고 GitHub Pages에 올립니다. GitHub 저장소에 이 폴더를 올리고, 저장소 Settings → Pages → Source를 "GitHub Actions"로 바꾸면 됩니다.

**블로그 글 중복 문제:** 블로그 글을 홈페이지에 그대로 옮기면 네이버가 유사문서로 판단해 블로그 노출이 떨어질 수 있습니다. 그래서 `daily/` 글 페이지는 `noindex`와 블로그 원문 `canonical`을 달아, 검색에는 블로그 원문만 잡히게 했습니다. 목록 페이지(`daily/index.html`)는 검색에 노출됩니다.

**인스타그램 주의:** 인스타그램은 공식 API 없이 공개 프로필을 읽습니다. 인스타그램이 막으면 마지막 저장본이 계속 보입니다. 안정적으로 쓰려면 Meta 개발자 계정의 Instagram Graph API 토큰으로 바꾸는 것이 좋습니다.

## 검색 결과 썸네일 (네이버·구글)

- 페이지마다 1200×630 공유 이미지(`images/og/`)를 자동으로 만들어 `og:image`로 넣었습니다. 카카오톡·네이버에 링크를 붙이면 이 이미지가 보입니다.
- `max-image-preview:large`, 구조화 데이터의 대표 이미지(`primaryImageOfPage`), 이미지 사이트맵(`sitemap.xml`의 `image:image`)을 넣어 검색엔진이 사진을 썸네일로 쓸 수 있게 했습니다.
- 검색 결과에 썸네일을 띄울지는 네이버와 구글이 정합니다. 사이트 등록 후 수집되기까지 보통 몇 주 걸립니다.

## AI·검색엔진이 잘 읽도록 넣은 것

- 모든 내용이 HTML 텍스트
- 페이지마다 제목, 설명, canonical, 요약 문단
- 구조화 데이터: LocalBusiness, Service, FAQPage, BreadcrumbList, Article, ImageGallery, VideoObject
- `sitemap.xml`(이미지 포함), `robots.txt`, `llms.txt`, `llms-full.txt`

## 수정하기

- 문구: `src/content.py`, `src/content_more.py`
- 도메인: `src/content.py`의 `SITE_URL`
- 네이버·구글 소유확인 코드: `src/content.py`에 `VERIFY = {"naver-site-verification": "코드", "google-site-verification": "코드"}` 추가
- 다시 만들기: `cd src && python3 build.py` (`--offline`을 붙이면 블로그·인스타를 새로 받지 않음)

## 배포 전에 할 일

1. `SITE_URL`을 실제 도메인으로 바꾸고 다시 빌드
2. 네이버 서치어드바이저, 구글 서치콘솔에 사이트 등록 → 소유확인 → `sitemap.xml` 제출
3. 네이버 플레이스, 인스타그램, 블로그 프로필에 홈페이지 주소 넣기
