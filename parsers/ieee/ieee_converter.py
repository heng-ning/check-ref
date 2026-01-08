from utils.text_processor import has_chinese
import re
def convert_en_ieee_to_apa(data):
    """
    將解析後的 IEEE 資料轉換為標準 APA 7 格式
    """
    # === 1. 作者 (Authors) ===
    apa_authors = []
    parsed = data.get('parsed_authors', [])
    
    # [New] 檢查最後一個作者是否為 et al.
    has_et_al = False
    if parsed and parsed[-1].get('last', '').lower().strip() in ['et al.', 'et al']:
        has_et_al = True
        # 暫時移除 et al. 以便處理前面的正常作者
        real_authors = parsed[:-1]
    else:
        real_authors = parsed

    if real_authors:
        for auth in real_authors:
            last = auth.get('last', '').strip()
            first = auth.get('first', '').strip()
            if len(first) == 1 and first.isalpha(): first += "."
            
            # 中文名不加逗號空格，英文名加
            if has_chinese(last):
                apa_authors.append(last)
            else:
                if first:
                    apa_authors.append(f"{last}, {first}")
                else:
                    apa_authors.append(last) # 只有 Last Name 的情況
                
    elif data.get('authors'):
        # 如果沒有 parsed_authors，直接用原始字串
        # 這裡也要簡單處理一下 et al.
        raw_auth = data['authors'].strip()
        if raw_auth.lower().endswith('et al.'):
            has_et_al = True
            raw_auth = re.sub(r',?\s+et\s+al\.?$', '', raw_auth, flags=re.IGNORECASE)
        apa_authors.append(raw_auth)

    # 組合作者字串
    if not apa_authors:
        auth_str = ""
    elif len(apa_authors) == 1:
        auth_str = apa_authors[0]
    elif len(apa_authors) == 2:
        # 如果原本有 et al.，就不應該用 & 連接，改用逗號
        if has_et_al:
            auth_str = f"{apa_authors[0]}, {apa_authors[1]}"
        else:
            auth_str = f"{apa_authors[0]} & {apa_authors[1]}"
    else:
        # 3人以上
        if has_et_al:
            # 如果有 et al.，全部用逗號連接，最後一個前面也不加 &
            auth_str = ", ".join(apa_authors)
        else:
            # 標準 APA: A, B, & C
            auth_str = ", ".join(apa_authors[:-1]) + f", & {apa_authors[-1]}"
    
    # [New] 最後加上 et al.
    if has_et_al:
        if auth_str:
            auth_str += ", et al."
        else:
            auth_str = "et al." # 理論上不會發生，但防呆

    # 只有當結尾不是點的時候才加點 (et al. 已經有點了，但 APA 規定括號前通常要有點)
    # 不過 APA 7 規定作者群後要有點。若結尾是 et al.，則變成 "et al."
    if auth_str and not auth_str.endswith('.'): 
        auth_str += "."

    # === 2. 年份 (Year) ===
    year_str = ""
    if data.get('year'):
        clean_year = str(data['year']).replace('(', '').replace(')', '').strip()
        year_str = f"({clean_year})."

    # === 3. 標題 (Title) ===
    title_str = data.get('title', '').strip()
    if title_str:
        title_str = title_str.rstrip(',.;') 
        title_str += "."

    # === 4. 來源 (Source details) ===
    source_parts = []
    
    if data.get('source'): source_parts.append(f"*{data['source']}*")
    
    if data.get('volume'):
        vol_info = f"*{data['volume']}*" 
        if data.get('issue'): vol_info += f"({data['issue']})"
        source_parts.append(vol_info)
    elif data.get('issue'):
        source_parts.append(f"({data['issue']})")
    
    if data.get('pages'): source_parts.append(data['pages'])

    source_str = ", ".join(source_parts)
    if source_str and not source_str.endswith('.'): source_str += "."

    # === 5. DOI / URL ===
    doi_str = ""
    if data.get('doi'):
        clean_doi = data['doi'].replace('doi:', '').strip()
        clean_doi = clean_doi.replace('https://doi.org/', '').replace('http://dx.doi.org/', '')
        doi_str = f"https://doi.org/{clean_doi}"
    elif data.get('url'):
        doi_str = data['url']

    # === 最終組合 ===
    parts = [p for p in [auth_str, year_str, title_str, source_str, doi_str] if p]
    return " ".join(parts)