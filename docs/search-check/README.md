# 네이버 검색 노출 점검

- `naver_check.js`: 키워드마다 네이버 PC 검색 1페이지를 열어 gangsanjawon.com 링크가 있는지 기록하고, 있으면 그 위치를 캡처합니다.
  실행: `SHOT_DIR=<저장 폴더> node docs/search-check/naver_check.js "키워드1" "키워드2" ...` (전역 설치된 playwright 사용)
- `naver-2026-11-09.json`: 첫 점검 결과(기준). 다음 점검 결과와 키워드별로 비교합니다.
- 1페이지 노출 기준이며, 로그인·기기·지역에 따라 결과가 다를 수 있습니다.
