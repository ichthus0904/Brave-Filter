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
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"⚠️ 요청 실패 ({url}): {e}")
        return ""

def process_line(line):
    # 빈 줄 제거
    if not line or line.isspace():
        return None
    
    line = line.strip()

    # 합칠 때 방해되는 기존 필터의 '버전/타이틀' 메타데이터만 제거 (맨 위에 새로 쓸 것이므로)
    if line.startswith('!'):
        if line.startswith('!#'):  # !#if 등 조건부 전처리문 제거 (모든 룰 활성화)
            return None
        if any(x in line for x in ["! Title:", "! Version:", "! Expires:", "! Last updated:", "! Homepage:", "! checksum", "! Description:", "! Licence:"]):
            return None
        return line

    # 🛑 핵심: 그 외의 모든 차단 룰은 단 1글자도 지우지 않고 그대로 통과시킵니다.
    # 갤러리 필터 고유의 복잡한 정규식이나 ##+js 문법이 그대로 유지되어 배너를 완벽히 잡습니다.
    return line

if __name__ == "__main__":
    print("=== Brave 통합 필터 생성 시작 (원본 100% 무손실 병합) ===")

    clean = []
    seen = set()
    
    for name, url in FILTER_SOURCES:
        print(f"📥 {name} 가져오는 중...")
        raw = fetch(url)
        count = 0
        for raw_line in raw.splitlines():
            processed = process_line(raw_line)
            # 중복되는 룰만 한 번 걸러줌
            if processed and processed not in seen:
                seen.add(processed)
                clean.append(processed)
                count += 1
        print(f"   - {count:,} 개의 유효 규칙 추가됨.")

    # 한국 시간(KST) 기준 타임스탬프 (Brave 강제 업데이트 유도용)
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    version_str = now.strftime('%Y%m%d%H%M') 

    with open("brave_combined_filter.txt", "w", encoding="utf-8") as f:
        f.write("[Adblock Plus 2.0]\n")
        f.write("! Title: Combined Filter for Brave (Lossless)\n")
        f.write("! Description: List-KR과 갤러리 필터를 원본 손실 없이 합친 무손실 버전\n")
        f.write(f"! Version: {version_str}\n")
        f.write("! Expires: 12 hours\n")
        f.write("! Last updated: " + now.strftime('%Y-%m-%d %H:%M KST') + "\n")
        f.write("\n")
        f.write("\n".join(clean))

    print(f"✅ 생성 완료: brave_combined_filter.txt ({len(clean):,} lines)")
