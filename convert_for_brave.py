#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import urllib.request
import re
from datetime import datetime, timezone, timedelta

# 1. 가져올 필터 리스트
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

def is_supported(line):
    # Brave가 지원하지 않거나 모바일에서 무거운 문법들
    unsupported = [
        "##+js", "scriptlet", "$replace", "$rewrite", 
        "#$#", "#@#$#", "log:", ":has(", ":xpath("
    ]
    return not any(u in line for u in unsupported)

def process_line(line):
    # 공백 및 전처리 지시자(!#) 완전 제거
    if not line or line.isspace() or line.startswith('!#'):
        return None
    
    line = line.strip()

    if line.startswith('!'):
        # 합칠 때 방해되는 기존 메타데이터 제외
        if any(x in line for x in ["! Title:", "! Version:", "! Expires:", "! Last updated:", "! Homepage:", "! checksum"]):
            return None
        return line

    if not is_supported(line):
        return None

    # AdGuard 전용 가짜 클래스 숨김 제거
    line = line.replace(':remove()', '')

    # 복잡한 정규식(Regex) 기반 규칙은 안전하게 폐기 (웹사이트 깨짐 방지)
    if re.search(r'domain=~?/[^/]+/', line) or re.search(r'##/.+?/', line):
        if any(c in line for c in '()|[]{}+?^$\\'):
            return None

    return line

if __name__ == "__main__":
    print("=== Brave 통합 초경량 필터 생성 시작 ===")

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
        f.write("! Title: Combined Filter for Brave (Lite)\n")
        f.write("! Description: List-KR과 갤러리 필터를 합친 Brave 초경량/안전 최적화 버전\n")
        f.write(f"! Version: {version_str}\n")
        f.write("! Expires: 12 hours\n")
        f.write("! Last updated: " + now.strftime('%Y-%m-%d %H:%M KST') + "\n")
        f.write("\n")
        f.write("\n".join(clean))

    print(f"✅ 생성 완료: brave_combined_filter.txt ({len(clean):,} lines)")
