#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import urllib.request
from datetime import datetime, timezone, timedelta

# 대상 필터: 오직 List-KR 통합 버전
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
    # 공백 줄 제거
    if not line or line.isspace():
        return None
    
    line = line.strip()

    # 메타데이터 정리
    if line.startswith('!'):
        # uBO 전용 조건부 전처리문 무시 (모든 룰 활성화)
        if line.startswith('!#'):
            return None
        # 자체적으로 헤더를 새로 작성할 것이므로 기존 헤더 정보 제거
        if any(x in line for x in ["! Title:", "! Version:", "! Expires:", "! Last updated:", "! Homepage:", "! checksum", "! Description:", "! Licence:"]):
            return None
        return line

    # 🛑 Brave에서 "절대" 지원하지 않는 타 엔진 전용 문법 필터링 (용량 최적화)
    unsupported = [
        "##+js",       # uBlock Origin 자바스크립트 주입 문법 (Brave 미지원)
        "#%#",         # AdGuard 자바스크립트 주입 문법 (Brave 미지원)
        "#$#",         # AdGuard 특수 CSS 주입 문법
        "#@#$#",       # AdGuard 특수 CSS 예외 문법
        "$replace=",   # 응답 본문 변조 문법 (Brave 미지원)
        "$rewrite="    # 리디렉션 변조 문법 (Brave 미지원)
    ]
    if any(u in line for u in unsupported):
        return None

    # 그 외 정규식, :has() 등 Brave가 소화할 수 있는 핵심 규칙은 100% 보존
    return line

if __name__ == "__main__":
    print("=== Brave 전용 List-KR 최적화 생성 시작 ===")

    clean = []
    seen = set()
    
    print("📥 List-KR 원본 가져오는 중...")
    raw = fetch(LIST_KR_URL)
    
    count = 0
    for raw_line in raw.splitlines():
        processed = process_line(raw_line)
        # 중복 룰 방지
        if processed and processed not in seen:
            seen.add(processed)
            clean.append(processed)
            count += 1
            
    print(f"   - {count:,} 개의 유효 규칙 추가됨.")

    # 한국 시간(KST) 기준 타임스탬프 (12시간 강제 업데이트 유도용)
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    version_str = now.strftime('%Y%m%d%H%M') 

    # 기존 GitHub Actions 파일과 일치하도록 파일명 고정
    with open("brave_list_kr.txt", "w", encoding="utf-8") as f:
        f.write("[Adblock Plus 2.0]\n")
        f.write("! Title: List-KR for Brave (Optimized)\n")
        f.write("! Description: Brave 실드에 완벽히 최적화된 List-KR 단일 필터\n")
        f.write(f"! Version: {version_str}\n")
        f.write("! Expires: 12 hours\n")
        f.write("! Last updated: " + now.strftime('%Y-%m-%d %H:%M KST') + "\n")
        f.write("! Homepage: https://github.com/List-KR/List-KR\n")
        f.write("\n")
        f.write("\n".join(clean))

    print(f"✅ 생성 완료: brave_list_kr.txt ({len(clean):,} lines)")
