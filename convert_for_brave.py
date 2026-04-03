import urllib.request
import urllib.parse

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

        # 1. 외부 파일 합치기
        if line.startswith('!#include '):
            include_url = line.split(' ', 1)[1].strip()
            if not include_url.startswith('http'):
                include_url = urllib.parse.urljoin(url, include_url)
                
            result.append(f"! --- Start: {include_url} ---")
            result.extend(process_list(include_url, processed_urls))
            result.append(f"! --- End: {include_url} ---")
            continue

        # 2. Brave가 못 읽는 정규식 포함 규칙 무효화 (유튜브/치지직 오류 방지 및 용량 최적화)
        if 'domain=' in line:
            domain_part = line.split('domain=')[1]
            if '/' in domain_part or '[' in domain_part:
                result.append(f"! [Brave 비호환 규칙 무효화] {line}")
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
    print("변환 완료!")
