import re

def format_pages_display(pages):
    """格式化頁碼顯示：如果包含字母就不加 pp."""
    if not pages:
        return None
    if re.search(r'[A-Za-z]', pages):
        return pages  # S27–S31
    else:
        return f"pp. {pages}"  # pp. 123-456

# =============================================================================
# 格式轉換
# =============================================================================

def convert_en_apa_to_ieee(data):
    ieee_authors = []
    for auth in data.get('parsed_authors', []):
        ieee_authors.append(f"{auth['first']} {auth['last']}".strip())
    auth_str = ", ".join(ieee_authors)
    if len(ieee_authors) > 2: auth_str = re.sub(r', ([^,]+)$', r', and \1', auth_str)
    
    parts = []
    if auth_str: parts.append(auth_str + ",")
    if data.get('title'): parts.append(f'"{data["title"]},"')
    
    if data.get('source_type') == 'Book Chapter':
        if data.get('editors'): parts.append(f"{data['editors']},")
        if data.get('book_title'): parts.append(f"{data['book_title']},")
        if data.get('edition'): parts.append(f"{data['edition']},")
        if data.get('publisher'): parts.append(f"{data['publisher']},")
        if data.get('year'): parts.append(f"{data['year']},")
        if data.get('pages'): parts.append(f"pp. {data['pages']}.")
    elif data.get('source_type') == 'Conference Paper':
        # 會議論文集格式轉換
        if data.get('proceedings_title'): 
            parts.append(f"in {data['proceedings_title']},")
        if data.get('year'): parts.append(f"{data['year']},")
        if data.get('pages'): parts.append(f"pp. {data['pages']}.")
        if data.get('publisher'): parts.append(f"{data['publisher']}.")
    else:
        if data.get('source'):
            parts.append(f"{data['source']},")
            if data.get('volume'):
                volume_str = f"vol. {data['volume']}"
                if data.get('issue'):
                    issue_val = str(data['issue'])
                    if issue_val.isdigit() or re.match(r'^\d+[\-–—]\d+$', issue_val):
                        volume_str += f", no. {issue_val}"
                    else:
                        volume_str = f"vol. {data['volume']}({issue_val})"
                parts.append(volume_str + ",")
            
            # 優先處理 article_number，否則處理 pages
            if data.get('article_number'):
                parts.append(f"{data['article_number']},")
            elif data.get('pages'):
                pages_val = data['pages']
                if re.search(r'[A-Za-z]', pages_val):
                    parts.append(f"{pages_val},")
                else:
                    parts.append(f"pp. {pages_val},")
        elif data.get('publisher'):
            if data.get('edition'): parts.append(f"{data['edition']},")
            parts.append(f"{data['publisher']},")
        
        if data.get('month'): parts.append(f"{data['month']}")
        if data.get('year'): parts.append(f"{data['year']}.")
    
    if data.get('doi'): parts.append(f"doi: {data['doi']}.")
    elif data.get('url'): parts.append(f"[Online]. Available: {data['url']}")
    
    return " ".join(parts)

def convert_zh_apa_to_num(data):
    parts = []
    if isinstance(data.get('authors'), list): auth = "、".join(data.get('authors'))
    else: auth = data.get('authors', '')
    
    if auth: parts.append(auth)
    if data.get('year'): parts.append(data['year'])
    if data.get('title'): parts.append(f"「{data['title']}」")
    if data.get('source'): parts.append(f"《{data['source']}》")
    
    vol_issue = []
    if data.get('volume'): vol_issue.append(f"{data['volume']}卷")
    if data.get('issue'): vol_issue.append(f"{data['issue']}期")
    if vol_issue: parts.append("".join(vol_issue))
    if data.get('pages'): parts.append(data['pages'])
    if data.get('url'): parts.append(data['url'])
    
    return "，".join(parts) + "。"

def convert_zh_num_to_apa(data):
    parts = []
    if isinstance(data.get('authors'), list): auth = "、".join(data.get('authors'))
    else: auth = data.get('authors', '')
    
    parts.append(f"{auth}（{data.get('year', '無年份')}）")
    if data.get('title'): parts.append(data['title'])
    if data.get('source'):
        source_part = f"《{data['source']}》"
        if data.get('volume'):
            source_part += f"，{data['volume']}"
            if data.get('issue'): source_part += f"({data['issue']})"
        if data.get('pages'): source_part += f"，{data['pages']}"
        parts.append(source_part)
    if data.get('url'): parts.append(data['url'])
    
    return "。".join(parts) + "。"