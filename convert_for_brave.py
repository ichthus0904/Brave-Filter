#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import urllib.request
from datetime import datetime, timezone, timedelta

# 대상 필터: 오직 List-KR uBlock Origin 통합 버전
LIST_KR_URL = "https://cdn.jsdelivr.net/npm/@list-kr/filterslists@latest/dist/filterslist-uBlockOrigin-unified.txt"

def fetch(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Brave-Filter-Builder'})
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"⚠️ 요청 실패 ({url}): {e}")
        return ""

def process_line(line):
    # 1. 공백 줄 제거
    if not line or line.isspace():
        return None
    
    line = line.strip()

    # 2. 메타데이터 및 코멘트 정리
    if line.startswith('!'):
        # !#if, !#endif 등 uBO 전처리문 무시 (규칙 자체는 살림)
        if line.startswith('!#'):
            return None
        # 자체 헤더를 생성할 것이므로 기존 헤더 제거 (일반 코멘트는 유지)
        metadata_headers = ["! Title:", "! Version:", "! Expires:", "! Last updated:", 
                            "! Homepage:", "! checksum", "! Description:", "! Licence:"]
        if any(line.startswith(x) for x in metadata_headers):
            return None
        return line

    # 3. 🛑 Brave 미지원 문법 필터링 (용량 최적화 및 파싱 에러 방지)
    # 참고: Brave는 uBlock Origin의 ##+js (스크립트릿), $redirect, $removeparam 등을 네이티브로 완벽 지원하므로 제거하면 안 됩니다!
    unsupported = [
        "##^",         # uBO HTML 응답 본문 필터링 (Brave 미지원)
        "$replace=",   # uBO 응답 본문 텍스트 변조 (Brave 미지원)
        "#%#",         # AdGuard 자바스크립트 주입 문법
        "#$#",         # AdGuard 특수 CSS 주입 문법
        "#@#$#",       # AdGuard 특수 CSS 예외 문법
        "$rewrite="    # AdGuard 리디렉션 변조 (uBO는 $redirect 사용)
    ]
    
    if any(u in line for u in unsupported):
        return None

    # 그 외 스크립트릿(##+js), 절차적 꾸미기 필터(:has 등)는 Brave가 소화 가능하므로 보존
    return line

if __name__ == "__main__":
    print("=== Brave 전용 List-KR 최적화 생성 시작 ===")

    clean = []
    seen = set()
    
    print("📥 List-KR 원본 가져오는 중...")
    raw = fetch(LIST_KR_URL)
    
    count = 0
    # 성능 최적화를 위해 splitlines() 활용
    for raw_line in raw.splitlines():
        processed = process_line(raw_line)
        # 중복 룰 방지 및 유효성 검사
        if processed and processed not in seen:
            seen.add(processed)
            clean.append(processed)
            count += 1
            
    print(f"   - {count:,} 개의 유효 규칙 추가됨.")

    # 한국 시간(KST) 기준 타임스탬프
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    version_str = now.strftime('%Y%m%d%H%M') 

    # Brave에 찰떡같이 인식되는 표준 Adblock Plus 헤더 포맷
    with open("brave_list_kr.txt", "w", encoding="utf-8") as f:
        f.write("[Adblock Plus 2.0]\n")
        f.write("! Title: List-KR for Brave (Optimized)\n")
        f.write("! Description: Brave 실드에 완벽히 최적화된 List-KR 단일 필터\n")
        f.write(f"! Version: {version_str}\n")
        f.write("! Expires: 12 hours\n")
        f.write(f"! Last updated: {now.strftime('%Y-%m-%d %H:%M KST')}\n")
        f.write("! Homepage: https://github.com/List-KR/List-KR\n")
        f.write("\n")
        f.write("\n".join(clean))
        f.write("\n")

    print(f"✅ 생성 완료: brave_list_kr.txt ({len(clean):,} lines)")
