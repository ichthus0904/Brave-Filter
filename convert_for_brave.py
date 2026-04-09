import urllib.request
import urllib.parse
import re
from datetime import datetime, timezone, timedelta

def wildcard_convert(domain_pattern):
    """정규식 도메인 패턴을 Brave-friendly wildcard(*)로 변환"""
    pattern = domain_pattern.strip('/')
    # ^ $ 제거
    pattern = pattern.replace('^', '').replace('$', '')
    # 이스케이프 제거
    pattern = pattern.replace('\\.', '.').replace('\\', '')
    # 숫자 관련 정규식 → *
    pattern = re.sub(r'\[0-9\]\+|\d\+\+?|\[0-9\]\*', '*', pattern)
    pattern = re.sub(r'\[0-9\]', '*', pattern)
    # 기타 흔한 패턴 정리
    pattern = re.sub(r'\[\^.\]\*', '*', pattern)
    return pattern.strip()

def process_line(line):
    line = line.strip()
    if not line:
        return None

    # 주석 처리
    if line.startswith('!'):
        if line.startswith('!#include '):
            return line  # include는 그대로 두고 process_list에서 처리
        return line

    # scriptlet (+js) 규칙은 Brave에서 대부분 동작 안 하므로 주석 처리
    if '+js' in line or '##+js' in line:
        return f"! [Brave skipped - scriptlet] {line}"

    # [$domain=...] 또는 domain= 처리 (가장 중요)
    if '[$domain=' in line or ',domain=' in line or '$domain=' in line:
        # [$domain=/regex/] 형태 찾기
        match = re.search(r'\[\$?domain=([^,\]]+)', line)
        if match:
            domain_part = match.group(1)
            if domain_part.startswith('/') and domain_part.endswith('/'):
                wildcard = wildcard_convert(domain_part)
                # [$domain=...] 부분을 wildcard로 교체
                new_domain = f"domain={wildcard}" if not line.startswith('[$') else f"[$domain={wildcard}]"
                line = line.replace(match.group(0), new_domain)
            else:
                # 이미 일반 도메인인 경우 그대로
                pass

    # cosmetic 규칙에서 도메인 부분에 regex가 있는 경우 (예: /tvwiki[0-9]+.com/##...)
    if '##' in line or '#$#' in line or '#?#' in line:
        sep = '##' if '##' in line else '#$#' if '#$#' in line else '#?#'
        if sep in line:
            parts = line.split(sep, 1)
            if len(parts) == 2:
                domain_part = parts[0]
                rule_part = parts[1]
                if '/' in domain_part and ('[0-9]' in domain_part or '\\d' in domain_part):
                    # 도메인 부분이 regex인 경우
                    domains = domain_part.split(',')
                    new_domains = []
                    for d in domains:
                        d = d.strip()
                        if d.startswith('/') and d.endswith('/'):
                            new_d = wildcard_convert(d)
                            new_domains.append(new_d)
                        else:
                            new_domains.append(d)
                    line = f"{','.join(new_domains)}{sep}{rule_part}"

    return line

def process_list(url, processed_urls=None):
    if processed_urls is None:
        processed_urls = set()
    if url in processed_urls:
        return []
    processed_urls.add(url)

    print(f"Fetching: {url}")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as response:
            content = response.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"오류 발생 ({url}): {e}")
        return [f"! Error fetching {url}"]

    lines = content.splitlines()
    result = []

    for line in lines:
        processed = process_line(line)
        if processed is None:
            continue

        if processed.startswith('!#include '):
            include_url = processed.split(' ', 1)[1].strip()
            if not include_url.startswith('http'):
                include_url = urllib.parse.urljoin(url, include_url)
            result.append(f"! --- include start: {include_url} ---")
            result.extend(process_list(include_url, processed_urls))
            result.append(f"! --- include end: {include_url} ---")
        else:
            result.append(processed)

    return result

if __name__ == "__main__":
    main_url = "https://cdn.jsdelivr.net/npm/@list-kr/filterslists@latest/dist/filterslist-uBlockOrigin-unified.txt"
    
    print("List-KR → Brave Shields용 와일드카드 변환 시작... (B 방식)")
    
    final_lines = process_list(main_url)

    # 중복 제거 (순서 유지)
    seen = {}
    clean_lines = []
    for line in final_lines:
        if line not in seen:
            seen[line] = True
            clean_lines.append(line)

    # 한국 시간 (KST) 기준 버전 생성
    kst = timezone(timedelta(hours=9))
    current_time = datetime.now(kst).strftime('%Y%m%d_%H%M')

    with open("brave_list-kr.txt", "w", encoding="utf-8") as f:
        f.write("[Adblock Plus 2.0]\n")
        f.write("! Title: List-KR Unified for Brave Shields\n")
        f.write("! Description: List-KR을 Brave Shields에 최적화한 버전 (regex → wildcard 변환)\n")
        f.write(f"! Version: {current_time}\n")
        f.write("! Expires: 12 hours\n")
        f.write("! Homepage: https://github.com/List-KR/List-KR\n")
        f.write("! Last updated: " + datetime.now(kst).strftime('%Y-%m-%d %H:%M KST') + "\n")
        f.write("\n")
        
        f.write("\n".join(clean_lines))

    print(f"완료! → brave_list-kr.txt 생성됨 ({len(clean_lines)} lines)")
    print("GitHub Actions에 이 스크립트를 올리고, raw 파일 URL을 Brave에 추가하면 됩니다.")
