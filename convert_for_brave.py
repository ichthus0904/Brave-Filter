import urllib.request
import urllib.parse
import re

MAX_RANGE = 50  # 숫자가 2개 이상 연속될 경우 기하급수적으로 늘어나므로 50~100 추천
MAX_DOMAINS_PER_RULE = 500 # 메모리 보호를 위한 최대 도메인 확장 제한

def resolve_numbers(text):
    """정규식 내의 숫자 패턴([0-9]+, \d 등)을 찾아 재귀적으로 모든 경우의 수를 생성합니다."""
    # 숫자 정규식 패턴 매칭
    match = re.search(r'\[0-9\]\+|\\d\+|\[0-9\]|\\d', text)
    if not match:
        # 이스케이프 문자 정리 후 반환
        return [text.replace('\\', '')]

    pattern_found = match.group(0)
    is_plus = '+' in pattern_found
    limit = MAX_RANGE if is_plus else 9

    results = []
    prefix = text[:match.start()]
    suffix = text[match.end():]

    for i in range(limit + 1):
        new_text = f"{prefix}{i}{suffix}"
        # 재귀 호출을 통해 두 번째, 세 번째 숫자 패턴도 모두 변환
        sub_results = resolve_numbers(new_text)
        results.extend(sub_results)
        
        # 무한 증식 방지
        if len(results) > MAX_DOMAINS_PER_RULE:
            break

    return results

def expand_domain_regex(pattern):
    """Brave가 지원하지 않는 도메인 정규식을 일반 도메인 리스트로 변환"""
    pattern = pattern.strip('/')
    pattern = pattern.replace('^', '').replace('$', '').replace('\\.', '.')

    # 1. (a|b) 형태의 그룹 처리
    group_match = re.search(r'\(([^)]+)\)', pattern)
    bases = []
    if group_match:
        options = group_match.group(1).split('|')
        for opt in options:
            bases.append(pattern.replace(group_match.group(0), opt))
    else:
        # 그룹이 없으면 전체 문자열에 대한 | 처리
        bases = pattern.split('|')

    # 2. 숫자 정규식 확장
    domains = []
    for base in bases:
        domains.extend(resolve_numbers(base))
        
    return list(set(domains)) # 중복 제거 후 반환


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

        if line.startswith('!'):
            # include 병합
            if line.startswith('!#include '):
                include_url = line.split(' ', 1)[1].strip()
                if not include_url.startswith('http'):
                    include_url = urllib.parse.urljoin(url, include_url)

                result.append(f"! --- include start: {include_url} ---")
                result.extend(process_list(include_url, processed_urls))
                result.append(f"! --- include end: {include_url} ---")
            else:
                result.append(line)
            continue

        # 1. CSS/Cosmetic 규칙 처리 (##, #?#)
        if '##' in line or '#?#' in line:
            sep = '##' if '##' in line else '#?#'
            parts = line.split(sep, 1)

            if len(parts) == 2:
                domain_part, rule_part = parts

                # 도메인 파트에 정규식이 포함된 경우 (예: a.com,/regex/,b.com)
                if '/' in domain_part:
                    domain_list = domain_part.split(',')
                    expanded_domains = []
                    is_valid = True

                    for d in domain_list:
                        if d.startswith('/') and d.endswith('/'):
                            expanded = expand_domain_regex(d)
                            if expanded:
                                expanded_domains.extend(expanded)
                            else:
                                is_valid = False
                        else:
                            expanded_domains.append(d)

                    if is_valid and expanded_domains:
                        # 여러 줄로 쪼개지 않고 쉼표(,)로 묶어서 한 줄로 최적화 (Brave 성능 향상)
                        joined_domains = ','.join(expanded_domains)
                        result.append(f"{joined_domains}{sep}{rule_part}")
                        continue
                    else:
                        result.append(f"! [정규식 미지원 제외] {line}")
                        continue

        # 2. Network 규칙 내 domain= 처리
        if 'domain=' in line:
            match = re.search(r'domain=([^,]+)', line)
            if match:
                domain_string = match.group(1)
                domain_parts = domain_string.split('|') # a.com|/regex/|~b.com 분리
                new_domain_parts = []
                modified = False

                for dp in domain_parts:
                    is_negated = dp.startswith('~')
                    core_dp = dp[1:] if is_negated else dp

                    if core_dp.startswith('/') and core_dp.endswith('/'):
                        expanded = expand_domain_regex(core_dp)
                        if expanded:
                            for ed in expanded:
                                new_domain_parts.append(('~' if is_negated else '') + ed)
                            modified = True
                        else:
                            new_domain_parts.append(dp)
                    else:
                        new_domain_parts.append(dp)

                if modified:
    unique_domains = list(set(new_domain_parts))

    if len(unique_domains) > MAX_DOMAINS_PER_RULE:
        result.append(f"! [domain 확장 초과로 제외] {line}")
        continue

    for d in unique_domains:
        new_line = line.replace(f"domain={domain_string}", f"domain={d}")
        result.append(new_line)

    continue

        # 정규식 치환이 필요 없는 일반 규칙
        result.append(line)

    return result


if __name__ == "__main__":
    main_url = 'https://cdn.jsdelivr.net/npm/@list-kr/filterslists@latest/dist/filterslist-uBlockOrigin-unified.txt'

    print("Brave 최적화 필터 변환 시작...")

    final_lines = process_list(main_url)

    # 중복 제거 (순서 유지)
    final_lines = list(dict.fromkeys(final_lines))

    output_filename = 'brave_list-kr_optimized.txt'

    with open(output_filename, 'w', encoding='utf-8') as f:
        f.write('\n'.join(final_lines))

    print(f"완료: {output_filename}")
