#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import urllib.request
import re
import os
from datetime import datetime, timezone, timedelta

# ==========================================
# 1. Brave 정규식 변환 함수 (이스케이프 처리 강화)
# ==========================================
def to_brave_wildcard(pattern):
    if not pattern:
        return pattern
    
    p = str(pattern).strip()
    is_negated = False
    
    if p.startswith('~'):
        is_negated = True
        p = p[1:]
        
    p = p.strip(' /^$')
    
    # 이스케이프 문자열 사전 처리 (\/, \. 복구 등)
    p = p.replace('\\/', '/')
    p = p.replace('\\.', '.')
    p = p.replace('\\', '')
    
    # 정규식 패턴을 와일드카드(*)로 변환
    p = re.sub(r'\[0-9\]\+?|\d\+\+?|\[a-zA-Z0-9\]\+?', '*', p)
    p = re.sub(r'\[\^.\]\*?', '*', p)
    p = re.sub(r'\.\*|\.\+', '*', p)
    p = re.sub(r'\([^)]+\)', '*', p)
    p = re.sub(r'[\[\]\(\)\^$]', '', p)
    p = re.sub(r'\*+', '*', p) # 중복 와일드카드 압축

    if '*' in p and not p.endswith('*'):
        p = p.rstrip('*.') + '*'
        
    if is_negated:
        p = '~' + p
        
    return p.strip()

# ==========================================
# 2. 메인 처리 로직 (단순화 및 정교화)
# ==========================================
def process_unified_list():
    url = "https://cdn.jsdelivr.net/npm/@list-kr/filterslists@latest/dist/filterslist-uBlockOrigin-unified.txt"
    
    print(f"다운로드 중: {url}")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; Brave-Filter-Converter)'})
        with urllib.request.urlopen(req, timeout=20) as response:
            content = response.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"다운로드 실패: {e}")
        return[], {}

    headers = {}
    header_keys =["Title:", "Description:", "Version:", "Expires:", "Homepage:", "License:", "Updated:"]
    
    brave_lines =[]
    
    for raw in content.splitlines():
        line = raw.strip()
        if not line:
            continue

        # 1) 헤더 수집 (break 제거 및 정확도 향상)
        if line.startswith('! '):
            for key in header_keys:
                if line.startswith(f"! {key}") and key not in headers:
                    headers[key] = line
            brave_lines.append(line)
            continue

        # 2) 주석 및 Brave 미지원 스크립틀릿 스킵
        if line.startswith('!'):
            brave_lines.append(line)
            continue
            
        if '##+js' in line or '#@#+js' in line or '#$#+js' in line:
            brave_lines.append(f"! [Brave skipped scriptlet] {line}")
            continue

        # 3) 네트워크 규칙 변환 (조건 엄격화: 주석 제외, 옵션 기호 [,$] 확인)
        if re.search(r'[,\$]domain=', line):
            line = re.sub(
                r'([,\$]domain=)(~?)/([^/]+)/',
                lambda m: f"{m.group(1)}{m.group(2)}{to_brave_wildcard(m.group(3))}",
                line
            )

        # 4) 코스메틱 필터 복잡한 도메인 정규식 변환
        for sep in ['##', '#@#', '#$#', '#?#']:
            if sep in line:
                parts = line.split(sep, 1)
                if len(parts) == 2:
                    domain_part = parts[0]
                    if any(x in domain_part for x in ['[0-9]', '\\d', '^', '$', '.*', '/']):
                        new_domains =[]
                        for d in domain_part.split(','):
                            d = d.strip()
                            clean_d = d[1:] if d.startswith('~') else d
                            if (clean_d.startswith('/') and clean_d.endswith('/')) or any(c in clean_d for c in ['[0-9]', '^', '$', '\\']):
                                new_domains.append(to_brave_wildcard(d))
                            else:
                                new_domains.append(d)
                        line = ','.join(filter(None, new_domains)) + sep + parts[1]
                break

        brave_lines.append(line)

    # 5) 스마트 중복 제거 (주석 보존, 룰만 제거)
    clean_lines =[]
    seen_rules = set()
    
    for line in brave_lines:
        if line.startswith('!') or not line:
            clean_lines.append(line)
        else:
            if line not in seen_rules:
                seen_rules.add(line)
                clean_lines.append(line)

    return clean_lines, headers

# ==========================================
# 실행부
# ==========================================
if __name__ == "__main__":
    print(f"=== Brave Shields 최적화 스크립트 시작 ===\n시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 처리 실행
    brave_lines, headers = process_unified_list()
    
    if not brave_lines:
        print("필터 처리에 실패했습니다. 스크립트를 종료합니다.")
        exit(1)

    # 출력 폴더 준비
    os.makedirs("./dist", exist_ok=True)
    
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    brave_version = now.strftime('%Y%m%d_%H%M')

    output_filename = "./dist/brave_list-kr.txt"
    
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write("[Adblock Plus 2.0]\n")
        f.write("! Title: List-KR for Brave Shields\n")
        f.write("! Description: List-KR Unified을 Brave Shields에 최적화한 버전\n")
        f.write(f"! Brave Version: {brave_version}\n")
        f.write("! Expires: 12 hours\n")
        f.write(f"! Converted: {now.strftime('%Y-%m-%d %H:%M KST')}\n")
        f.write("! Source: Local Personal Script\n")
        f.write("\n")
        
        f.write("! ================== Original List-KR Information ==================\n")
        # 수집된 원본 헤더 출력
        for key in ["Title:", "Version:", "Updated:", "Description:", "Homepage:", "License:"]:
            if key in headers:
                f.write(headers[key] + "\n")
        f.write("! ==================================================================\n\n")
        
        f.write("\n".join(brave_lines))

    print(f"\n✅ 파일 저장 완료: {output_filename} (총 {len(brave_lines):,} 줄)")
    print("✨ 모든 작업이 완료되었습니다!")
