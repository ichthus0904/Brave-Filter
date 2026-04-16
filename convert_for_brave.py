#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import urllib.request
import re
import os
from datetime import datetime, timezone, timedelta

# ==========================================
# 1. Brave 정규식 → 와일드카드 변환 (안정 + 호환 통합)
# ==========================================
def to_brave_wildcard(pattern):
    if not pattern:
        return pattern

    p = str(pattern).strip()
    is_negated = False

    if p.startswith('~'):
        is_negated = True
        p = p[1:]

    p = p.strip(' /^$')

    # 이스케이프 복구
    p = p.replace('\\/', '/').replace('\\.', '.').replace('\\', '')

    # 정규식 → 와일드카드
    p = re.sub(r'\[0-9\]\+?|\d\+\+?|\[a-zA-Z0-9\]\+?', '*', p)
    p = re.sub(r'\[\^.\]\*?', '*', p)
    p = re.sub(r'\.\*|\.\+', '*', p)
    p = re.sub(r'\([^)]+\)', '*', p)
    p = re.sub(r'[\[\]\(\)\^$]', '', p)
    p = re.sub(r'\*+', '*', p)

    if '*' in p and not p.endswith('*'):
        p = p.rstrip('*.') + '*'

    if is_negated:
        p = '~' + p

    return p.strip()


# ==========================================
# 2. domain 변환 (정확도 + 호환성 균형)
# ==========================================
def convert_domain_option(line):
    if not re.search(r'[,\$\[]domain=', line):
        return line

    def replace_domain(match):
        prefix = match.group(1)
        value = match.group(2)

        new_values = []
        for part in value.split('|'):
            part = part.strip()
            if not part:
                continue

            clean_part = part[1:] if part.startswith('~') else part

            # ✔ 핵심 전략
            # 1. /regex/ → 반드시 변환
            # 2. 명확한 정규식 문자만 허용
            # 3. 일반 도메인은 절대 유지

            if (clean_part.startswith('/') and clean_part.endswith('/')) or \
               any(c in clean_part for c in ['[', '^', '$', '\\']):
                new_values.append(to_brave_wildcard(part))
            else:
                new_values.append(part)

        return prefix + '|'.join(new_values)

    return re.sub(r'([,\$\[]domain=)([^,\s\]]+)', replace_domain, line)


# ==========================================
# 3. 메인 처리
# ==========================================
def process_list():
    url = "https://cdn.jsdelivr.net/npm/@list-kr/filterslists@latest/dist/filterslist-uBlockOrigin-unified.txt"

    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=20) as response:
            content = response.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"다운로드 실패: {e}")
        return [], {}

    headers = {}
    brave_lines = []
    skipped_scriptlets = 0

    for raw in content.splitlines():
        line = raw.strip()

        if not line:
            brave_lines.append(line)
            continue

        # Adblock 헤더 제거
        if line == "[Adblock Plus 2.0]":
            continue

        # ==========================================
        # ✔ 헤더 처리 (엄격 + 유연 hybrid)
        # ==========================================
        if line.startswith('! '):
            normalized = line.replace(" ", "")

            for key in ["Title:", "Description:", "Version:", "Expires:", "Homepage:", "License:", "Updated:"]:
                if normalized.startswith(f"!{key}") and key not in headers:
                    headers[key] = line

            brave_lines.append(line)
            continue

        # 일반 주석
        if line.startswith('!'):
            brave_lines.append(line)
            continue

        # scriptlet 제거
        if '##+js' in line or '#@#+js' in line or '#$#+js' in line:
            brave_lines.append(f"! [Brave skipped scriptlet] {line}")
            skipped_scriptlets += 1
            continue

        # domain 처리
        line = convert_domain_option(line)

        # 코스메틱 필터 도메인 처리
        for sep in ['##', '#@#', '#$#', '#?#']:
            if sep in line:
                parts = line.split(sep, 1)
                if len(parts) == 2:
                    domain_part = parts[0]

                    if any(x in domain_part for x in ['[0-9]', '\\d', '^', '$', '.*', '/']):
                        new_domains = []
                        for d in domain_part.split(','):
                            d = d.strip()
                            clean_d = d[1:] if d.startswith('~') else d

                            if (clean_d.startswith('/') and clean_d.endswith('/')) or \
                               any(c in clean_d for c in ['[0-9]', '^', '$', '\\']):
                                new_domains.append(to_brave_wildcard(d))
                            else:
                                new_domains.append(d)

                        line = ','.join(filter(None, new_domains)) + sep + parts[1]
                break

        brave_lines.append(line)

    # ==========================================
    # 중복 제거
    # ==========================================
    clean_lines = []
    seen = set()

    for line in brave_lines:
        if line.startswith('!') or not line:
            clean_lines.append(line)
        elif line not in seen:
            seen.add(line)
            clean_lines.append(line)

    print(f"✔ scriptlet 제거: {skipped_scriptlets}개")
    return clean_lines, headers


# ==========================================
# 4. 실행
# ==========================================
if __name__ == "__main__":
    print("=== Brave 완성형 필터 생성 시작 ===")

    lines, headers = process_list()

    if not lines:
        print("실패")
        exit(1)

    os.makedirs("./dist", exist_ok=True)

    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)

    with open("./dist/brave_ultimate.txt", "w", encoding="utf-8") as f:
        f.write("[Adblock Plus 2.0]\n")
        f.write("! Title: Brave Ultimate Filter\n")
        f.write("! Description: 안정성 + 차단력 최적화 통합 버전\n")
        f.write(f"! Updated: {now.strftime('%Y-%m-%d %H:%M KST')}\n")
        f.write("! Expires: 12 hours\n\n")

        f.write("! ===== Original List Info =====\n")
        for k in headers:
            f.write(headers[k] + "\n")
        f.write("! =============================\n\n")

        f.write("\n".join(lines))

    print("\n✅ 완료 → dist/brave_ultimate.txt 생성됨")
