#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import urllib.request
from datetime import datetime, timezone, timedelta

# 대상 필터: List-KR (Classic 버전으로 변경됨)
LIST_KR_CLASSIC_URL = "https://cdn.jsdelivr.net/npm/@list-kr/filterslists@latest/dist/filterslist-uBlockOrigin-classic.txt"

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

    # 1. 메타데이터 및 불필요한 주석 정리
    if line.startswith('!'):
        # uBO 조건부 전처리문 무시 (!#if 등)
        if line.startswith('!#'):
            return None
        # 새로 헤더를 덮어씌울 것이므로 기존 메타데이터 제거
        if any(x in line for x in ["! Title:", "! Version:", "! Expires:", "! Last updated:", "! Homepage:", "! checksum", "! Description:", "! Licence:"]):
            return None
        return line

    # 2. Brave 실드에서 "절대" 지원하지 않는 문법 정밀 타격 (용량 다이어트)
    unsupported = [
        "##+js",       # uBlock Origin JS 주입 (Brave 미지원)
        "#%#",         # AdGuard JS 주입 (Brave 미지원)
        "#$#",         # AdGuard 특수 CSS 주입
        "#@#$#",       # AdGuard 특수 CSS 예외
        "$replace=",   # 응답 본문 변조 (Brave 미지원)
        "$rewrite="    # 리디렉션 변조 (Brave 미지원)
    ]
    
    if any(u in line for u in unsupported):
        return None

    # 3. 그 외 Brave가 소화할 수 있는 정규식, :has(), 일반 CSS 숨김 규칙 등은 100% 살림
    return line

if __name__ == "__main__":
    print("=== Brave 전용 List-KR (Classic) 최적화 생성 시작 ===")

    clean = []
    seen = set()
    
    print("📥 List-KR Classic 원본 가져오는 중...")
    raw = fetch(LIST_KR_CLASSIC_URL)
    
    count = 0
    for raw_line in raw.splitlines():
        processed = process_line(raw_line)
        # 중복 룰 걸러내기
        if processed and processed not in seen:
            seen.add(processed)
            clean.append(processed)
            count += 1
            
    print(f"   - {count:,} 개의 유효 규칙 추가됨.")

    # 12시간 자동 업데이트 강제 유도용 타임스탬프 (KST 기준)
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    version_str = now.strftime('%Y%m%d%H%M') 

    # GitHub Action(.yml)의 git add 파일명과 동일하게 설정
    with open("brave_list_kr.txt", "w", encoding="utf-8") as f:
        f.write("[Adblock Plus 2.0]\n")
        f.write("! Title: List-KR Classic for Brave\n")
        f.write("! Description: Brave 실드에 완벽히 최적화된 List-KR Classic 단일 필터\n")
        f.write(f"! Version: {version_str}\n")
        f.write("! Expires: 12 hours\n")
        f.write("! Last updated: " + now.strftime('%Y-%m-%d %H:%M KST') + "\n")
        f.write("! Homepage: https://github.com/List-KR/List-KR\n")
        f.write("\n")
        f.write("\n".join(clean))

    print(f"✅ 생성 완료: brave_list_kr.txt ({len(clean):,} lines)")
