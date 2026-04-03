import urllib.request
import urllib.parse
import re

def expand_domain_regex(pattern):
    # 정규식 기호 제거 및 정리
    if pattern.startswith('/'): pattern = pattern[1:]
    if pattern.endswith('/'): pattern = pattern[:-1]
    pattern = pattern.replace('^', '').replace('$', '').replace('\\.', '.')
    
    domains = []
    # | 기호로 여러 사이트가 묶인 경우 분리해서 처리
    for part in pattern.split('|'):
        part = part.strip()
        # [0-9]+ 가 포함된 불법사이트 패턴일 경우 0~200까지 생성
        if '[0-9]+' in part:
            try:
                prefix, suffix = part.split('[0-9]+', 1)
                for i in range(0, 201):
                    domains.append(f"{prefix}{i}{suffix}")
            except ValueError:
                domains.append(part)
        # [0-9] 단일 숫자일 경우 0~9까지 생성
        elif '[0-9]' in part:
            try:
                prefix, suffix = part.split('[0-9]', 1)
                for i in range(0, 10):
                    domains.append(f"{prefix}{i}{suffix}")
            except ValueError:
                domains.append(part)
        else:
            domains.append(part.replace('\\', ''))
            
    return domains

def process_list(url, processed_urls=None):
    if processed_urls is None:
        processed_urls = set()

    if url in processed_urls:
        return []
    processed_urls.add(url)

    print(f"Fetching: {url}")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            lines = response.read().decode('utf-8').splitlines()
    except Exception as e:
        print(f"오류 발생 ({url}): {e}")
        return [f"! Error fetching {url}"]

    result = []
    for line in lines:
        line = line.strip()
        if not line: continue

        # 1. !#include 구문 완벽 병합 (외부 파일을 모두 하나로 합침)
        if line.startswith('!#include '):
            include_url = line.split(' ', 1)[1].strip()
            if not include_url.startswith('http'):
                include_url = urllib.parse.urljoin(url, include_url)
            result.append(f"! --- 병합 시작: {include_url} ---")
            result.extend(process_list(include_url, processed_urls))
            result.append(f"! --- 병합 끝: {include_url} ---")
            continue

        # 2. ## 또는 #?# (이미지/배너 숨김 규칙) 처리
        if ('##' in line or '#?#' in line) and line.startswith('/'):
            sep = '##' if '##' in line else '#?#'
            domain_part, rule_part = line.split(sep, 1)
            
            # 정규식 도메인일 경우
            if domain_part.startswith('/') and domain_part.endswith('/'):
                if '[0-9]' in domain_part:
                    # 200개로 풀어서 '단 1줄'의 가벼운 코드로 압축
                    domains = expand_domain_regex(domain_part)
                    line = f"{','.join(domains)}{sep}{rule_part}"
                else:
                    # 숫자 확장이 아닌 알 수 없는 복잡한 정규식은 무효화 (유튜브 오류 방지)
                    result.append(f"! [안전 무효화] {line}")
                    continue

        # 3. $domain= (네트워크 차단 규칙) 처리
        elif 'domain=' in line:
            match = re.search(r'domain=(/[^/]+/)', line)
            if match:
                regex_str = match.group(1)
                if '[0-9]' in regex_str:
                    # 200개로 풀어서 | 기호로 단 1줄에 묶음
                    domains = expand_domain_regex(regex_str)
                    expanded_str = "domain=" + "|".join(domains)
                    line = line.replace("domain=" + regex_str, expanded_str)
                else:
                    # 복잡한 정규식은 무효화
                    result.append(f"! [안전 무효화] {line}")
                    continue

        result.append(line)

    return result

if __name__ == "__main__":
    main_url = 'https://cdn.jsdelivr.net/npm/@list-kr/filterslists@latest/dist/filterslist-uBlockOrigin-unified.txt'
    print("Brave용 List-KR 필터 변환을 시작합니다...")
    final_lines = process_list(main_url)
    
    output_filename = 'brave_list-kr.txt'
    with open(output_filename, 'w', encoding='utf-8') as f:
        f.write('\n'.join(final_lines))
        
    print(f"변환 완료! 최적화된 파일이 생성되었습니다.")
