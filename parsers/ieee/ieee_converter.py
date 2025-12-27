from utils.text_processor import has_chinese

def convert_en_ieee_to_apa(data):
    """
    將解析後的 IEEE 資料轉換為標準 APA 7 格式
    """
    # === 1. 作者 (Authors) ===
    apa_authors = []
    parsed = data.get('parsed_authors', [])
    
    if parsed:
        for auth in parsed:
            last = auth.get('last', '').strip()
            first = auth.get('first', '').strip()
            if len(first) == 1 and first.isalpha(): first += "."
            
            # 中文名不加逗號空格，英文名加
            if has_chinese(last):
                apa_authors.append(last)
            else:
                apa_authors.append(f"{last}, {first}")
                
    elif data.get('authors'):
        apa_authors.append(data['authors'])

    # 組合作者字串
    if not apa_authors:
        auth_str = ""
    elif len(apa_authors) == 1:
        auth_str = apa_authors[0]
    elif len(apa_authors) == 2:
        auth_str = f"{apa_authors[0]} & {apa_authors[1]}"
    else:
        auth_str = ", ".join(apa_authors[:-1]) + f", & {apa_authors[-1]}"
    
    if auth_str and not auth_str.endswith('.'): auth_str += "."

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