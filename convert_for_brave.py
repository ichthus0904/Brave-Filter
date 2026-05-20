#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import urllib.request
from datetime import datetime, timezone, timedelta

# 병합할 필터 소스
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
    # 공백 줄 제거
    if not line or line.isspace():
        return None
    
    line = line.strip()

    # 메타데이터 정리: 맨 위에 새로 작성할 정보나 쓸모없는 전처리 지시자 제거
    if line.startswith('!'):
        if line.startswith('!#'):  # uBO 조건부 전처리문(!#if 등) 무시 (모든 룰 활성화)
            return None
        if any(x in line for x in ["! Title:", "! Version:", "! Expires:", "! Last updated:", "! Homepage:", "! checksum", "! Description:", "! Licence:"]):
            return None
        return line

    # 🛑 Brave에서 "절대" 지원하지 않아 용량만 차지하는 타 엔진 전용 문법 필터링
    unsupported = [
        "##+js(",      # uBlock Origin 전용 자바스크립트 주입 문법
        "#%#",         # AdGuard 전용 자바스크립트 주입 문법
        "#$#",         # AdGuard 전용 특수 CSS 주입 문법
        "#@#$#",       # AdGuard 전용 특수 CSS 예외 문법
        "$replace=",   # AdGuard 전용 네트워크 응답 변조 문법
        "$rewrite="    # AdGuard 전용 네트워크 리디렉션 문법
    ]
    if any(u in line for u in unsupported):
        return None

    # 위 문법들을 제외한 복잡한 정규식(Regex)이나 :has() 같은 강력한 CSS 선택자는
    # Brave 모바일 엔진이 지원하거나 자체적으로 스킵하므로 "원본 그대로" 통과시킵니다.
    return line

if __name__ == "__main__":
    print("=== Brave 통합 최적화 필터 생성 시작 (유효 룰 보존) ===")

    clean = []
    seen = set()
    
    for name, url in FILTER_SOURCES:
        print(f"📥 {name} 가져오는 중...")
        raw = fetch(url)
        count = 0
        for raw_line in raw.splitlines():
            processed = process_line(raw_line)
            # 중복 룰 방지 (두 필터 간 겹치는 규칙 1개로 통일)
            if processed and processed not in seen:
                seen.add(processed)
                clean.append(processed)
                count += 1
        print(f"   - {count:,} 개의 유효 규칙 추가됨.")

    # 한국 시간(KST) 기준 타임스탬프 (Brave 브라우저 12시간 강제 업데이트 유도용)
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    version_str = now.strftime('%Y%m%d%H%M') 

    # ❗주의: 파일명을 기존 GitHub Actions 설정과 동일한 brave_list_kr.txt 로 고정
    with open("brave_list_kr.txt", "w", encoding="utf-8") as f:
        f.write("[Adblock Plus 2.0]\n")
        f.write("! Title: List-KR + Gallery Filter for Brave\n")
        f.write("! Description: 두 필터의 핵심 룰은 살리고 Brave 미지원 문법만 쳐낸 최적화 버전\n")
        f.write(f"! Version: {version_str}\n")
        f.write("! Expires: 12 hours\n")
        f.write("! Last updated: " + now.strftime('%Y-%m-%d %H:%M KST') + "\n")
        f.write("\n")
        f.write("\n".join(clean))

    print(f"✅ 생성 완료: brave_list_kr.txt ({len(clean):,} lines)")
