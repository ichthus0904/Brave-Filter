#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import urllib.request
from datetime import datetime, timezone, timedelta

FILTER_SOURCES = [
    ("List-KR", "https://cdn.jsdelivr.net/npm/@list-kr/filterslists@latest/dist/filterslist-uBlockOrigin-unified.txt"),
    ("Gallery-Filter", "https://raw.githubusercontent.com/hooray804/adguard-gallery-filter/refs/heads/main/filter.txt")
]

def fetch(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Brave-Filter-Builder'})
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"⚠️ 요청 실패 ({url}): {e}")
        return ""

def process_line(line):
    # 공백 및 전처리 지시자(!#) 제거
    if not line or line.isspace() or line.startswith('!#'):
        return None
    
    line = line.strip()

    # 합칠 때 방해되는 기존 메타데이터 제거 (맨 위에 새로 작성하므로)
    if line.startswith('!'):
        if any(x in line for x in ["! Title:", "! Version:", "! Expires:", "! Last updated:", "! Homepage:", "! checksum"]):
            return None
        return line

    # 🛑 수정된 부분: 핵심 차단 룰(:has, 정규식 등)은 그대로 살려둡니다.
    # Brave에서 정말로 아무 쓸모가 없거나 에러를 내는 uBlock/AdGuard 전용 스크립트 구문만 최소한으로 거릅니다.
    unsupported = [
        "##+js",       # uBO 자바스크립트 주입 (Brave 미지원)
        "$replace",    # AdGuard 전용 문법 (Brave 미지원)
        "$rewrite",    # AdGuard 전용 문법 (Brave 미지원)
        "#$#",         # AdGuard 스니펫 (Brave 미지원)
        "#@#$#"        # AdGuard 스니펫 예외 (Brave 미지원)
    ]
    if any(u in line for u in unsupported):
        return None

    # :remove() 나 정규식을 지우는 코드는 모두 삭제했습니다. 
    # 원본 필터 규칙을 그대로 유지하여 배너를 완벽하게 차단합니다.

    return line

if __name__ == "__main__":
    print("=== Brave 통합 필터 생성 시작 (차단율 100% 복구 버전) ===")

    clean = []
    seen = set()
    
    for name, url in FILTER_SOURCES:
        print(f"📥 {name} 가져오는 중...")
        raw = fetch(url)
        count = 0
        for raw_line in raw.splitlines():
            processed = process_line(raw_line)
            if processed and processed not in seen:
                seen.add(processed)
                clean.append(processed)
                count += 1
        print(f"   - {count:,} 개의 유효 규칙 추가됨.")

    # 한국 시간(KST) 기준 타임스탬프 및 버전 생성
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    version_str = now.strftime('%Y%m%d%H%M') 

    with open("brave_combined_filter.txt", "w", encoding="utf-8") as f:
        f.write("[Adblock Plus 2.0]\n")
        f.write("! Title: Combined Filter for Brave\n")
        f.write("! Description: List-KR과 갤러리 필터를 합친 버전 (원본 룰 보존)\n")
        f.write(f"! Version: {version_str}\n")
        f.write("! Expires: 12 hours\n")
        f.write("! Last updated: " + now.strftime('%Y-%m-%d %H:%M KST') + "\n")
        f.write("\n")
        f.write("\n".join(clean))

    print(f"✅ 생성 완료: brave_combined_filter.txt ({len(clean):,} lines)")
