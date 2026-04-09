import urllib.request
import urllib.parse
import re
# 👇 (추가됨) 시간을 생성하기 위한 모듈 추가
from datetime import datetime, timezone, timedelta

MAX_RANGE = 50
MAX_DOMAINS_PER_RULE = 300  # Actions 안정성 고려 (500 → 300 권장)


def resolve_numbers(text):
    match = re.search(r'\[0-9\]\+|\\d\+|\[0-9\]|\\d', text)
    if not match:
        return [text.replace('\\', '')]

    pattern_found = match.group(0)
    is_plus = '+' in pattern_found
    limit = MAX_RANGE if is_plus else 9

    results = []
    prefix = text[:match.start()]
    suffix = text[match.end():]

    for i in range(limit + 1):
        new_text = f"{prefix}{i}{suffix}"
        sub_results = resolve_numbers(new_text)
        results.extend(sub_results)

        if len(results) > MAX_DOMAINS_PER_RULE:
            break

    return results


def expand_domain_regex(pattern):
    pattern = pattern.strip('/')
    pattern = pattern.replace('^', '').replace('$', '').replace('\\.', '.')

    group_match = re.search(r'\(([^)]+)\)', pattern)

    bases = []
    if group_match:
        options = group_match.group(1).split('|')
        for opt in options:
            bases.append(pattern.replace(group_match.group(0), opt))
    else:
        bases = pattern.split('|')

    domains = []
    for base in bases:
        domains.extend(resolve_numbers(base))

    # 중복 제거 + 개수 제한
    domains = list(set(domains))

    if len(domains) > MAX_DOMAINS_PER_RULE:
        return []

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
        with urllib.request.urlopen(req, timeout=10) as response:
            lines = response.read().decode('utf-8', errors='ignore').splitlines()
    except Exception as e:
        print(f"오류 발생 ({url}): {e}")
        return [f"! Error fetching {url}"]

    result = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 주석 처리
        if line.startswith('!'):
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

        # -----------------------------
        # CSS 규칙 처리
        # -----------------------------
        if '##' in line or '#?#' in line:
            sep = '##' if '##' in line else '#?#'
            parts = line.split(sep, 1)

            if len(parts) == 2:
                domain_part, rule_part = parts

                if '/' in domain_part:
                    domain_list = domain_part.split(',')
                    expanded_domains = []

                    for d in domain_list:
                        if d.startswith('/') and d.endswith('/'):
                            expanded = expand_domain_regex(d)
                            if not expanded:
                                expanded_domains = []
                                break
                            expanded_domains.extend(expanded)
                        else:
                            expanded_domains.append(d)

                    expanded_domains = list(set(expanded_domains))

                    if not expanded_domains:
                        result.append(f"! [정규식 미지원 제외] {line}")
                        continue

                    # 너무 많으면 분할
                    chunk_size = 100
                    for i in range(0, len(expanded_domains), chunk_size):
                        chunk = expanded_domains[i:i+chunk_size]
                        result.append(f"{','.join(chunk)}{sep}{rule_part}")

                    continue

        # -----------------------------
        # domain= 처리 (핵심)
        # -----------------------------
        if 'domain=' in line:
            match = re.search(r'domain=([^,]+)', line)

            if match:
                domain_string = match.group(1)
                domain_parts = domain_string.split('|')

                new_domain_parts = []
                modified = False

                for dp in domain_parts:
                    is_negated = dp.startswith('~')
                    core = dp[1:] if is_negated else dp

                    if core.startswith('/') and core.endswith('/'):
                        expanded = expand_domain_regex(core)

                        if expanded:
                            for e in expanded:
                                new_domain_parts.append(('~' if is_negated else '') + e)
                            modified = True
                        else:
                            new_domain_parts.append(dp)
                    else:
                        new_domain_parts.append(dp)

                if modified:
                    unique_domains = list(set(new_domain_parts))

                    if len(unique_domains) > MAX_DOMAINS_PER_RULE:
                        result.append(f"! [domain 확장 초과 제외] {line}")
                        continue

                    # 🔥 Brave 핵심: 한 줄 → 여러 줄 분리
                    for d in unique_domains:
                        new_line = line.replace(f"domain={domain_string}", f"domain={d}")
                        result.append(new_line)

                    continue

        result.append(line)

    return result


if __name__ == "__main__":
    main_url = "https://cdn.jsdelivr.net/npm/@list-kr/filterslists@latest/dist/filterslist-uBlockOrigin-unified.txt"

    print("Brave 필터 변환 시작...")

    final_lines = process_list(main_url)

    # 1. 기존 리스트에 이미 존재하는 버전/헤더/만료일 태그 제거 (중복 방지)
    clean_lines = []
    for line in final_lines:
        if line.startswith("[Adblock Plus 2.0]") or line.startswith("! Version:") or line.startswith("! Expires:"):
            continue
        clean_lines.append(line)

    # 2. 중복 제거 (순서 유지)
    clean_lines = list(dict.fromkeys(clean_lines))

    # 👇 (추가됨) 한국 시간(KST) 기준으로 현재 시간 생성 (버전용)
    kst = timezone(timedelta(hours=9))
    current_time = datetime.now(kst).strftime('%Y%m%d%H%M')

    # 👇 (추가됨) 파일 작성 시 헤더를 맨 위에 먼저 쓰도록 수정
    with open("brave_list-kr.txt", "w", encoding="utf-8") as f:
        # 브레이브 자동 업데이트를 위한 필수 헤더 작성
        f.write("[Adblock Plus 2.0]\n")
        f.write("! Title: List-KR for Brave\n")
        f.write(f"! Version: {current_time}\n")  # 파이썬 실행 시각이 버전이 됨
        f.write("! Expires: 12 hours\n")       # 12시간 간격으로 업데이트 지시
        f.write("\n")                          # 헤더와 본문 사이 한 줄 띄우기
        
        # 실제 필터 내용 작성
        f.write("\n".join(clean_lines))

    print("완료: brave_list-kr.txt")
