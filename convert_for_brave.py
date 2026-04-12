import urllib.request
import urllib.parse
import re
from datetime import datetime, timezone, timedelta

def to_brave_wildcard(pattern):
    if not pattern:
        return pattern
    
    p = str(pattern).strip()
    
    # 1. 예외(Negation) 처리 수정 (is_negated 버그 해결)
    is_negated = False
    if p.startswith('~'):
        is_negated = True
        p = p[1:]
        
    # 앞뒤 슬래시 및 정규식 시작/끝 기호 제거
    p = p.strip(' /^$')

    # 2. 정규식 패턴을 와일드카드로 변환
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

def process_list(url, processed=None, header_dict=None):
    if processed is None:
        processed = set()
    if header_dict is None:
        header_dict = {}  # 리스트 대신 딕셔너리 사용 (중복 헤더 방지)
        
    if url in processed:
        return [], header_dict
    processed.add(url)

    print(f"Fetching: {url}")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; Brave-Filter-Converter)'})
        with urllib.request.urlopen(req, timeout=20) as response:
            content = response.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return [f"! Error fetching {url}"], header_dict

    result = []
    
    for raw in content.splitlines():
        line = raw.strip()
        if not line:
            continue

        # 3. 원본 헤더 수집 (메인 파일의 헤더만 최우선으로 수집되도록 dict 활용)
        if line.startswith('! '):
            for key in ["Title:", "Description:", "Version:", "Expires:", "Homepage:", "License:", "Updated:"]:
                if key in line and key not in header_dict:
                    header_dict[key] = line
            continue  # 일반 주석 및 헤더는 파싱에서 제외

        # include 처리
        if line.startswith('!#include '):
            result.append(f"! [Included] {line}")
            inc_url = line.split(maxsplit=1)[1].strip()
            if not inc_url.startswith('http'):
                inc_url = urllib.parse.urljoin(url, inc_url)
            inc_result, inc_headers = process_list(inc_url, processed, header_dict)
            result.extend(inc_result)
            # header_dict는 dict 참조이므로 자동 업데이트 됨
            continue

        # scriptlet 처리 (Brave에서 지원안하는 uBO 특화 스크립트 스킵)
        if '##+js' in line or '#@#+js' in line or '#$#+js' in line:
            result.append(f"! [Brave skipped scriptlet] {line}")
            continue

        # 4. 네트워크 규칙 domain 정규식 변환 ($domain=/regex/ 또는 ,domain=/regex/)
        line = re.sub(
            r'([,\$]domain=)(~?)/([^/]+)/',
            lambda m: f"{m.group(1)}{m.group(2)}{to_brave_wildcard(m.group(3))}",
            line
        )

        # 5. 코스메틱 필터 변환
        for sep in ['##', '#@#', '#$#', '#?#']:
            if sep in line:
                parts = line.split(sep, 1)
                if len(parts) == 2:
                    domain_part = parts[0]
                    # 도메인 파트에 정규식 문법이 있을 경우에만 변환 시도
                    if any(x in domain_part for x in ['[0-9]', '\\d', '^', '$', '.*', '/']):
                        new_domains = []
                        for d in domain_part.split(','):
                            d = d.strip()
                            clean_d = d[1:] if d.startswith('~') else d
                            # 정규식 형태(/.../)이거나 정규식 기호가 포함된 경우만 변환
                            if (clean_d.startswith('/') and clean_d.endswith('/')) or any(c in clean_d for c in ['[0-9]', '^', '$', '\\']):
                                new_domains.append(to_brave_wildcard(d))
                            else:
                                new_domains.append(d)
                                
                        line = ','.join(filter(None, new_domains)) + sep + parts[1]
                break

        result.append(line)

    return result, header_dict

if __name__ == "__main__":
    main_url = "https://cdn.jsdelivr.net/npm/@list-kr/filterslists@latest/dist/filterslist-uBlockOrigin-unified.txt"
    print("=== List-KR → Brave Shields 변환 시작 ===")

    final_lines, final_headers = process_list(main_url)

    # 중복 제거 (Python 3.7+ 에서는 dict.fromkeys를 쓰면 순서 유지하며 중복 제거 가능)
    clean_lines = list(dict.fromkeys(line for line in final_lines if line.strip()))

    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    version = now.strftime('%Y%m%d_%H%M')

    with open("brave_list-kr.txt", "w", encoding="utf-8") as f:
        # Brave용 커스텀 헤더
        f.write("[Adblock Plus 2.0]\n")
        f.write("! Title: List-KR for Brave Shields\n")
        f.write("! Description: List-KR Unified을 Brave Shields에 최적화한 버전\n")
        f.write(f"! Brave Version: {version}\n")
        f.write("! Expires: 12 hours\n")
        f.write("! Converted: " + now.strftime('%Y-%m-%d %H:%M KST') + "\n")
        f.write("! Source: https://github.com/ichthus0904/Brave-Filter\n")
        f.write("\n")
        
        # 수집된 원본 필터 헤더 (중복 없이 메인 파일 정보만 출력됨)
        f.write("! ================== Original List-KR Information ==================\n")
        for key in ["Title:", "Version:", "Updated:", "Description:", "Homepage:", "License:"]:
            if key in final_headers:
                f.write(final_headers[key] + "\n")
        f.write("! =================================================================\n\n")
        
        # 필터 룰 본문
        f.write("\n".join(clean_lines))

    print(f"✅ 변환 완료! 총 {len(clean_lines):,} 줄")
