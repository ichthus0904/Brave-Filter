import urllib.request
import urllib.parse
import re

def expand_domain_regex(pattern):
    """
    정규식(예: /tvwiki[0-9]+\.net/)을 입력받아 
    tvwiki0.net 부터 tvwiki200.net 까지의 목록으로 확장합니다.
    """
    if pattern.startswith('/'):
        pattern = pattern[1:]
    if pattern.endswith('/'):
        pattern = pattern[:-1]
        
    pattern = pattern.replace('^', '').replace('$', '').replace('\\.', '.')
    
    domains = []
    for part in pattern.split('|'):
        part = part.strip()
        if '[0-9]+' in part:
            try:
                prefix, suffix = part.split('[0-9]+', 1)
                # 0번부터 200번 사이트까지 모두 생성 (tvwiki14 등 모두 포함됨)
                for i in range(0, 201):
                    domains.append(f"{prefix}{i}{suffix}")
            except ValueError:
                domains.append(part)
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
        if not line:
            continue

        # 1. !#include 구문 병합
        if line.startswith('!#include '):
            include_url = line.split(' ', 1)[1].strip()
            if not include_url.startswith('http'):
                include_url = urllib.parse.urljoin(url, include_url)
                
            result.append(f"! --- Start of included list: {include_url} ---")
            result.extend(process_list(include_url, processed_urls))
            result.append(f"! --- End of included list: {include_url} ---")
            continue

        # 2. 이미지/배너 숨김 규칙(##) 도메인 확장 (예: /^tvwiki[0-9]+\.net$/##.banner)
        if ('##' in line or '#?#' in line) and line.startswith('/'):
            sep = '##' if '##' in line else '#?#'
            domain_part, rule_part = line.split(sep, 1)
            
            if domain_part.startswith('/') and domain_part.endswith('/'):
                domains = expand_domain_regex(domain_part)
                expanded_domains_str = ",".join(domains) # Brave는 , 로 구분
                line = f"{expanded_domains_str}{sep}{rule_part}"

        # 3. 네트워크 차단 규칙의 $domain= 확장 (예: ...$domain=/tvwiki[0-9]+\.net/)
        elif 'domain=' in line:
            match = re.search(r'domain=(/[^/]+/)', line)
            if match:
                regex_str = match.group(1)
                if '[0-9]' in regex_str:
                    domains = expand_domain_regex(regex_str)
                    expanded_domains_str = "domain=" + "|".join(domains) # Brave는 | 로 구분
                    line = line.replace("domain=" + regex_str, expanded_domains_str)

        result.append(line)

    return result

if __name__ == "__main__":
    main_url = 'https://cdn.jsdelivr.net/npm/@list-kr/filterslists@latest/dist/filterslist-uBlockOrigin-unified.txt'
    print("Brave용 List-KR 필터 변환을 시작합니다...")
    final_lines = process_list(main_url)
    output_filename = 'brave_list-kr.txt'
    with open(output_filename, 'w', encoding='utf-8') as f:
        f.write('\n'.join(final_lines))
    print(f"\n변환 완료! '{output_filename}' 파일이 생성되었습니다.")
