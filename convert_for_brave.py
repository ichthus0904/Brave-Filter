#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import urllib.request
import re
from datetime import datetime, timezone, timedelta

MAIN_URL = "https://cdn.jsdelivr.net/npm/@list-kr/filterslists@latest/dist/filterslist-uBlockOrigin-unified.txt"

def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Brave-Filter-Builder'})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode('utf-8', errors='ignore')

def extract_version(lines):
    for line in lines:
        if line.startswith("! Version:"):
            return line.replace("! ", "").strip()
    return "Version: unknown"

def is_supported(line):
    # 제안하신 대로 미지원 축소 (Brave 엔진이 자체적으로 무시하거나 향후 지원할 문법은 남겨둠)
    unsupported = [
        "##+js",
        "scriptlet"
    ]
    return not any(u in line for u in unsupported)

def safe_wildcard(pattern):
    if not pattern:
        return None
    p = pattern.strip('/^$')
    
    # 숫자 패턴만 안전하게 와일드카드로 변환
    if '[0-9]' in p or '\\d' in p:
        p = re.sub(r'\[0-9\]\+?', '*', p)
        p = re.sub(r'\\d\+?', '*', p)
    else:
        return None  # 복잡한 정규식은 변환 거부
        
    # 여전히 위험/복잡한 정규식 기호가 남아있다면 중단
    if any(x in p for x in ['(', ')', '|']):
        return None
        
    p = p.replace('\\.', '.').replace('\\', '')
    p = re.sub(r'[\[\]\^$]', '', p)
    return p.strip()

def process_line(line):
    if not line or line.isspace():
        return None
    line = line.strip()

    # 주석 및 메타데이터 처리
    if line.startswith('!'):
        if line.startswith('!#if') or line.startswith('!#endif') or line.startswith('!#else'):
            return None # uBO 전용 전처리 지시자만 깔끔하게 제거
        if any(x in line for x in["! Title:", "! Version:", "! Expires:", "! Last updated:", "! Homepage:", "! Licence:"]):
            return None
        return line

    if not is_supported(line):
        return f"! [Brave Unsupported Syntax] {line}"

    # Brave 미지원 속성 치환
    if ':remove()' in line:
        line = line.replace(':remove()', '')

    # 1. 네트워크 필터 ($domain=regex 처리)
    if 'domain=/' in line or 'domain=~/' in line:
        def domain_replace(match):
            prefix = match.group(1) # 'domain=' 또는 'domain=~'
            original = match.group(2) # 정규식 내용
            converted = safe_wildcard(original)
            if converted:
                return f"{prefix}{converted}"
            else:
                return "FAIL_MARKER"

        # 정규식 도메인 매칭 치환 (예: domain=/regex/ 또는 domain=~/regex/)
        new_line = re.sub(r'(domain=~?)/(.+?)/', domain_replace, line)
        
        # ⭐️ 제안하신 부분: 변환 실패 시 글로벌 도메인으로 풀지 않고 규칙 자체를 비활성화
        if "FAIL_MARKER" in new_line:
            return f"! [Brave removed domain regex] {line}"
        line = new_line

    # 2. 코스메틱 필터 (숨김 필터) 도메인 처리
    for sep in['##', '#@#', '#?#']:
        if sep in line:
            parts = line.split(sep, 1)
            domain_part = parts[0]
            
            if '/' not in domain_part:
                break

            new_domains =[]
            for d in domain_part.split(','):
                d = d.strip()
                if d.startswith('/') and d.endswith('/'):
                    conv = safe_wildcard(d)
                    if conv:
                        new_domains.append(conv)
                    else:
                        # ⭐️ 제안하신 부분 적용: 코스메틱 필터도 변환 불가능하면 규칙 통으로 주석 처리
                        return f"! [Brave removed domain regex] {line}"
                else:
                    new_domains.append(d)

            if new_domains:
                line = ','.join(new_domains) + sep + parts[1]
            break

    return line

if __name__ == "__main__":
    print("=== Brave 맞춤형 최적화 필터 생성 시작 ===")

    raw = fetch(MAIN_URL)
    raw_lines = raw.splitlines()

    source_version = extract_version(raw_lines)
    
    clean =[]
    seen = set()
    
    # 중복 제거 및 필터 처리
    for raw_line in raw_lines:
        processed = process_line(raw_line)
        if processed and processed not in seen:
            seen.add(processed)
            clean.append(processed)

    # 시간 기록 (KST 기준)
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)

    with open("brave_list_kr.txt", "w", encoding="utf-8") as f:
        f.write("[Adblock Plus 2.0]\n")
        f.write("! Title: List-KR for Brave (Optimized)\n")
        f.write("! Description: Brave 실드에 최적화된 List-KR 자동 업데이트 필터\n")
        f.write(f"! Version: {source_version}\n")
        f.write("! Expires: 12 hours\n")
        f.write("! Updated: " + now.strftime('%Y-%m-%d %H:%M KST') + "\n")
        f.write("! Homepage: https://github.com/List-KR/List-KR\n")
        f.write("\n")
        f.write("\n".join(clean))

    print(f"✅ 완료: {len(clean):,} lines (Version: {source_version})")
