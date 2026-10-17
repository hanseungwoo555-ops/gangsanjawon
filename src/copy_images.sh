#!/bin/sh
# 업스케일된 사진을 사이트 이미지 폴더로 복사 (b275_before.jpg -> images/cases/b275-before.jpg)
UP="$1"; DST="$(dirname "$0")/images/cases"; mkdir -p "$DST"
for f in "$UP"/*.jpg; do n=$(basename "$f" .jpg); cp "$f" "$DST/$(echo "$n" | sed 's/_/-/').jpg"; done
