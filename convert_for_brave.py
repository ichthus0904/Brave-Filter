import urllib.request
import urllib.parse
import re
from datetime import datetime, timezone, timedelta

def to_brave_wildcard(pattern):
    """정규식 도메인 패턴을 Brave Shields에 최적화된 와일드카드(*)로 변환"""
    if not pattern:
        return pattern
    
    p = str(pattern).strip(' /^$')
    p = p.replace('\\.', '.').replace('\\', '')
    
    # 숫자 관련 정규식 모두 *로 변환
    p = re.sub(r'\[0-9\]\+?|\d\+\+?|\[0-9\]', '*', p)
    p = re.sub(r'\[\^.\]\*?', '*', p)
    
    # 남은 괄호, ^, $ 제거
    p = re.sub(r'[\[\]\(\)\^$]', '', p)
    
    # *가 있으면 끝에 * 보장 (tvwiki* 형태)
    if '*' in p and not p.endswith('*'):
        p = p.rstrip('*.') + '*'
    
    return p.strip()

def process_line(line: str):
    if not line or line.isspace():
        return None
    line = line.strip()

    # 주석 처리
    if line.startswith('!'):
        if line.startswith('!#include '):
            return line
        # 원본 List-KR의 버전/만료 헤더는 Brave용으로 대체하므로 스킵
        if any(x in line for x in ["! Title:", "! Version:", "! Expires:", "! Last updated:"]):
            return None
        return line

    # scriptlet (+js)은 Brave에서 대부분 동작하지 않으므로 주석 처리
    if '+js' in line or '#+js' in line:
        return f"! [Brave skipped] {line}"

    # [$domain=/regex/] 또는 domain=/regex/ 강력 변환
    line = re.sub(
        r'(\[\$?domain=)/([^,/]+?)/',
        lambda m: f"[$domain={to_brave_wildcard(m.group(2))}]" 
                  if m.group(0).startswith('[$') 
                  else f"domain={to_brave_wildcard(m.group(2))}",
        line
    )

    # cosmetic 규칙 (##, #$#, #?#) 내부 regex 도메인 변환
    for sep in ['##', '#$#', '#?#']:
        if sep in line:
            parts = line.split(sep, 1)
            if len(parts) == 2:
                domain_part = parts[0]
                if any(x in domain_part for x in ['[0-9]', '\\d', '/^', '^', '$']):
                    new_domains = []
                    for d in domain_part.split(','):
                        d = d.strip()
                        if (d.startswith('/') and d.endswith('/')) or any(c in d for c in ['[0-9]', '^', '$']):
                            new_domains.append(to_brave_wildcard(d))
                        else:
                            new_domains.append(d)
                    line = ','.join(filter(None, new_domains)) + sep + parts[1]
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
    
    print("=== List-KR → Brave Shields 최적화 변환 시작 (B 방식 - Wildcard) ===")
    
    final_lines = process_list(main_url)

    # 중복 제거 (순서 유지)
    clean_lines = []
    seen = {}
    for line in final_lines:
        stripped = line.strip()
        if stripped and stripped not in seen:
            seen[stripped] = True
            clean_lines.append(line)

    # 한국 시간(KST) 버전 생성
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    version = now.strftime('%Y%m%d_%H%M')

    with open("brave_list-kr.txt", "w", encoding="utf-8") as f:
        f.write("[Adblock Plus 2.0]\n")
        f.write("! Title: List-KR for Brave Shields\n")
        f.write("! Description: List-KR Unified을 Brave Shields에 최적화한 버전 (Regex → Wildcard 변환)\n")
        f.write(f"! Version: {version}\n")
        f.write("! Expires: 12 hours\n")
        f.write("! Updated: " + now.strftime('%Y-%m-%d %H:%M KST') + "\n")
        f.write("! Source: https://github.com/ichthus0904/Brave-Filter\n")
        f.write("! Recommended: Use with Aggressive mode\n")
        f.write("\n")
        
        f.write("\n".join(clean_lines))

    print(f"✅ 변환 완료! 총 {len(clean_lines):,} 줄 생성")
    print("   파일: brave_list-kr.txt")
    print("   이제 GitHub에 업로드하고 Brave Shields에서 구독하세요.")
