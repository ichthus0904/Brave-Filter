import urllib.request
import urllib.parse
import re
from datetime import datetime, timezone, timedelta

def to_wildcard(pattern):
    """정규식 도메인을 Brave 최적화 와일드카드로 변환"""
    p = pattern.strip('/')
    p = p.replace('^', '').replace('$', '').replace('\\.', '.').replace('\\', '')
    p = re.sub(r'\[0-9\]\+?|\d\+\+?|\[0-9\]', '*', p)
    p = re.sub(r'\[\^.\]\*?', '*', p)
    p = re.sub(r'[\[\]]', '', p)  # 남은 괄호 제거
    return p.strip('*') + '*' if '*' in p else p  # 끝에 * 보장

def process_line(line: str):
    if not line or line.isspace():
        return None
    line = line.strip()

    if line.startswith('!'):
        if line.startswith('!#include '):
            return line
        return line

    # scriptlet 완전 주석 처리 (Brave 호환성 낮음)
    if '+js' in line or '#+js' in line:
        return f"! [Brave skipped] {line}"

    # domain=/regex/ 또는 [$domain=/regex/] 처리
    if 'domain=' in line:
        match = re.search(r'(\$?domain=)(/[^/]+/)', line)
        if match:
            prefix = match.group(1)
            regex_part = match.group(2)
            wildcard = to_wildcard(regex_part)
            line = line.replace(match.group(0), f"{prefix}{wildcard}")

    # cosmetic 규칙에서 도메인 regex 처리
    for sep in ['##', '#$#', '#?#']:
        if sep in line:
            parts = line.split(sep, 1)
            if len(parts) == 2:
                domain_part = parts[0]
                if any(x in domain_part for x in ['[0-9]', '\\d', '/']):
                    domains = [to_wildcard(d) if (d.startswith('/') and d.endswith('/')) else d 
                               for d in domain_part.split(',')]
                    line = ','.join(domains) + sep + parts[1]
                break

    return line

def process_list(url, processed=None):
    if processed is None:
        processed = set()
    if url in processed:
        return []
    processed.add(url)

    print(f"Fetching: {url}")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as r:
            content = r.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"Error {url}: {e}")
        return [f"! Error fetching {url}"]

    result = []
    for raw_line in content.splitlines():
        processed_line = process_line(raw_line)
        if processed_line is None:
            continue

        if processed_line.startswith('!#include '):
            inc_url = processed_line.split(maxsplit=1)[1].strip()
            if not inc_url.startswith('http'):
                inc_url = urllib.parse.urljoin(url, inc_url)
            result.append(f"! --- Include: {inc_url} ---")
            result.extend(process_list(inc_url, processed))
        else:
            result.append(processed_line)

    return result

if __name__ == "__main__":
    main_url = "https://cdn.jsdelivr.net/npm/@list-kr/filterslists@latest/dist/filterslist-uBlockOrigin-unified.txt"
    
    print("List-KR → Brave Shields (Wildcard B 방식) 변환 시작...")
    lines = process_list(main_url)

    # 중복 제거
    clean_lines = []
    seen = {}
    for line in lines:
        if line not in seen:
            seen[line] = True
            clean_lines.append(line)

    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    version = now.strftime('%Y%m%d_%H%M')

    with open("brave_list-kr.txt", "w", encoding="utf-8") as f:
        f.write("[Adblock Plus 2.0]\n")
        f.write("! Title: List-KR for Brave Shields\n")
        f.write("! Description: List-KR Unified 필터를 Brave Shields에 최적화 (Regex → Wildcard 변환)\n")
        f.write(f"! Version: {version}\n")
        f.write("! Expires: 12 hours\n")
        f.write("! Updated: " + now.strftime('%Y-%m-%d %H:%M KST') + "\n")
        f.write("! Source: https://github.com/ichthus0904/Brave-Filter\n")
        f.write("\n")
        f.write("\n".join(clean_lines))

    print(f"완료! 총 {len(clean_lines):,} 줄 생성됨 → brave_list-kr.txt")
