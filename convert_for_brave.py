import urllib.request
import urllib.parse
import re
from datetime import datetime, timezone, timedelta

def to_brave_wildcard(pattern):
    if not pattern:
        return pattern
    p = str(pattern).strip(' /^$')
    is_negated = p.startswith('~')
    if is_negated:
        p = p[1:].strip(' /^$')

    p = re.sub(r'\[0-9\]\+?|\d\+\+?|\[a-zA-Z0-9\]\+?', '*', p)
    p = re.sub(r'\[\^.\]\*?', '*', p)
    p = re.sub(r'\.\*|\.\+', '*', p)
    p = re.sub(r'\([^)]+\)', '*', p)
    p = p.replace('\\.', '.').replace('\\', '')
    p = re.sub(r'[\[\]\(\)\^$]', '', p)
    p = re.sub(r'\*+', '*', p)

    if '*' in p and not p.endswith('*'):
        p = p.rstrip('*.') + '*'
    if is_negated:
        p = '~' + p
    return p.strip()

def process_list(url, processed=None, original_headers=None):
    if processed is None:
        processed = set()
    if original_headers is None:
        original_headers = []
    if url in processed:
        return [], original_headers
    processed.add(url)

    print(f"Fetching: {url}")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; Brave-Filter-Converter)'})
        with urllib.request.urlopen(req, timeout=20) as response:
            content = response.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return [f"! Error fetching {url}"], original_headers

    result = []
    for raw in content.splitlines():
        line = raw.strip()
        if not line:
            continue

        # 원본 헤더 수집
        if line.startswith('! ') and any(k in line for k in ["Title:", "Description:", "Version:", "Expires:", "Homepage:", "License:"]):
            original_headers.append(line)
            continue  # Brave 헤더는 나중에 별도 출력

        if line.startswith('!'):
            if line.startswith('!#include '):
                result.append(line)
                inc_url = line.split(maxsplit=1)[1].strip()
                if not inc_url.startswith('http'):
                    inc_url = urllib.parse.urljoin(url, inc_url)
                inc_result, inc_headers = process_list(inc_url, processed, original_headers)
                result.extend(inc_result)
                original_headers.extend(inc_headers)
                continue
            result.append(line)
            continue

        # scriptlet 처리
        if '+js' in line or '#+js' in line:
            result.append(f"! [Brave skipped] {line}")
            continue

        # domain regex 변환
        line = re.sub(
            r'(\[\$?domain=)/([^,/]+?)/',
            lambda m: (f"[$domain={to_brave_wildcard(m.group(2))}]" if m.group(0).startswith('[$') else f"domain={to_brave_wildcard(m.group(2))}"),
            line
        )

        # cosmetic 변환
        for sep in ['##', '#@#', '#$#', '#?#']:
            if sep in line:
                parts = line.split(sep, 1)
                if len(parts) == 2:
                    domain_part = parts[0]
                    if any(x in domain_part for x in ['[0-9]', '\\d', '^', '$', '.*']):
                        new_domains = [to_brave_wildcard(d.strip()) if (d.strip().startswith('/') and d.strip().endswith('/')) or any(c in d for c in ['[0-9]', '^', '$']) else d.strip() 
                                       for d in domain_part.split(',')]
                        line = ','.join(filter(None, new_domains)) + sep + parts[1]
                break

        result.append(line)

    return result, original_headers

if __name__ == "__main__":
    main_url = "https://cdn.jsdelivr.net/npm/@list-kr/filterslists@latest/dist/filterslist-uBlockOrigin-unified.txt"
    print("=== List-KR → Brave Shields 변환 시작 ===")

    final_lines, original_headers = process_list(main_url)

    # 중복 제거
    seen = {}
    clean_lines = []
    for line in final_lines:
        key = line.strip()
        if key and key not in seen:
            seen[key] = True
            clean_lines.append(line)

    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    version = now.strftime('%Y%m%d_%H%M')

    with open("brave_list-kr.txt", "w", encoding="utf-8") as f:
        f.write("[Adblock Plus 2.0]\n")
        f.write("! Title: List-KR for Brave Shields\n")
        f.write("! Description: List-KR Unified을 Brave Shields에 최적화한 버전\n")
        f.write(f"! Brave Version: {version}\n")
        f.write("! Expires: 12 hours\n")
        f.write("! Updated: " + now.strftime('%Y-%m-%d %H:%M KST') + "\n")
        f.write("! Source: https://github.com/ichthus0904/Brave-Filter\n")
        f.write("\n")
        
        f.write("! ================== Original List-KR Information ==================\n")
        for h in original_headers:
            f.write(h + "\n")
        f.write("! =================================================================\n\n")
        
        f.write("\n".join(clean_lines))

    print(f"✅ 변환 완료! 총 {len(clean_lines):,} 줄")
