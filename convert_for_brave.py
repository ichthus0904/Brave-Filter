import urllib.request
import urllib.parse
import re

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

        if line.startswith('!#include '):
            include_url = line.split(' ', 1)[1].strip()
            if not include_url.startswith('http'):
                include_url = urllib.parse.urljoin(url, include_url)
                
            result.append(f"! --- Start of included list: {include_url} ---")
            result.extend(process_list(include_url, processed_urls))
            result.append(f"! --- End of included list: {include_url} ---")
            continue

        if 'domain=' in line and '[0-9]' in line:
            if re.search(r'domain=[^,]*\[0-9\]', line):
                line = re.sub(r'\$domain=[^,]+$', '', line)
                line = re.sub(r',domain=[^,]+', '', line)
                line = re.sub(r'\$domain=[^,]+,', '$', line)

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
