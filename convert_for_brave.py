import urllib.request
import urllib.parse
import re
from datetime import datetime, timezone, timedelta

# ================== 원본 헤더 저장용 변수 ==================
original_headers = []

def to_brave_wildcard(pattern):
    """정규식 도메인 패턴을 Brave에 안전한 와일드카드(*)로 변환"""
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

def process_line(line: str):
    global original_headers
    if not line or line.isspace():
        return None
    line = line.strip()

    # 원본 List-KR 헤더 수집 (Version, Expires 등)
    if line.startswith('! ') and any(keyword in line for keyword in ["Title:", "Description:", "Version:", "Expires:", "Homepage:", "Licence:"]):
        original_headers.append(line)
        # Brave용 파일에서는 원본 헤더를 나중에 별도 섹션으로 출력할 것이므로 여기서는 None 반환
        if any(keyword in line for keyword in ["! Title:", "! Description:", "! Version:", "! Expires:", "! Last updated:", "! Homepage:"]):
            return None

    if line.startswith('!'):
        if line.startswith('!#include '):
            return line
        return line

    # scriptlet 주석 처리
    if '+js' in line or '#+js' in line:
        return f"! [Brave skipped] {line}"

    # [$domain=...] 또는 domain= regex 변환
    line = re.sub(
        r'(\[\$?domain=)/([^,/]+?)/',
        lambda m: (f"[$domain={to_brave_wildcard(m.group(2))}]" if m.group(0).startswith('[$') else f"domain={to_brave_wildcard(m.group(2))}"),
        line
    )

    # cosmetic 규칙 내부 regex 도메인 변환
    for sep in ['##', '#@#', '#$#', '#?#']:
        if sep in line:
            parts = line.split(sep, 1)
            if len(parts) == 2:
                domain_part = parts[0]
                if any(x in domain_part for x in ['[0-9]', '\\d', '^', '$', '.*', '.+']):
                    new_domains = []
                    for d in domain_part.split(','):
                        d = d.strip()
                        if (d.startswith('/') and d.endswith('/')) or any(c in d for c in ['[0-9]', '^', '$', '\\d', '.*']):
                            new_domains.append(to_brave_wildcard(d))
                        else:
                            new_domains.append(d)
                    line = ','.join(filter(None, new_domains)) + sep + parts[1]
            break

    return line

def process_list(url, processed=None):
    global original_headers
    if processed is None:
        processed = set()
    if url in processed:
        return []
    processed.add(url)

    print(f"Fetching: {url}")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; Brave-Filter-Converter)'})
        with urllib.request.urlopen(req, timeout=20) as response:
            content = response.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return [f"! Error fetching {url}"]

    result = []
    for raw in content.splitlines():
        processed_line = process_line(raw)
        if processed_line is None:
            continue

        if processed_line.startswith('!#include '):
            inc_url = processed_line.split(maxsplit=1)[1].strip()
            if not inc_url.startswith('http'):
                inc_url = urllib.parse.urljoin(url, inc_url)
            result.append(f"! Include: {inc_url}")
            result.extend(process_list(inc_url, processed))
        else:
            result.append(processed_line)

    return result

if __name__ == "__main__":
    main_url = "https://cdn.jsdelivr.net/npm/@list-kr/filterslists@latest/dist/filterslist-uBlockOrigin-unified.txt"
    
    print("=== List-KR → Brave Shields 최적화 변환 시작 (Wildcard 방식) ===")
    
    global original_headers
    original_headers = []   # 초기화
    final_lines = process_list(main_url)

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
        f.write("! Description: List-KR Unified을 Brave Shields에 최적화한 버전 (Regex → Wildcard 변환)\n")
        f.write(f"! Brave Version: {version}\n")
        f.write("! Expires: 12 hours\n")
        f.write("! Updated: " + now.strftime('%Y-%m-%d %H:%M KST') + "\n")
        f.write("! Source: https://github.com/ichthus0904/Brave-Filter\n")
        f.write("\n")
        
        # ================== 원본 List-KR 정보 표시 ==================
        f.write("! ================== Original List-KR Information ==================\n")
        if original_headers:
            for header in original_headers:
                f.write(header + "\n")
        else:
            f.write("! Original version information not found.\n")
        f.write("! =================================================================\n")
        f.write("\n")
        
        f.write("\n".join(clean_lines))

    print(f"✅ 변환 완료! 총 {len(clean_lines):,} 줄 생성")
    print("   원본 List-KR Version 정보가 파일 상단에 추가되었습니다.")
