import re
from utils.text_processor import extract_doi

def parse_chinese_authors(author_str):
    """
    拆分中文作者字串為作者列表
    支援頓號(、)、中文逗號(，)、英文逗號(,) 分隔
    
    範例：
        "陳坤宏、林思玲、董維琇、陳璽任" → ["陳坤宏", "林思玲", "董維琇", "陳璽任"]
    """
    if not author_str: 
        return []
    
    # 移除結尾的「等」、「著」、「編」
    clean_str = re.sub(r'\s*(等|著|編)$', '', author_str)
    
    # 用頓號、中文逗號、英文逗號分割
    authors = re.split(r'[、，,]', clean_str)
    
    # 過濾空字串並去除首尾空白
    authors = [a.strip() for a in authors if a.strip()]
    
    return authors

def extract_apa_zh_detailed(ref_text):
    result = {
        'format': 'APA (ZH)', 'lang': 'ZH',
        'authors': [], 'year': None, 'title': None, 'source': None,
        'volume': None, 'issue': None, 'pages': None,
        'url': None,
        'doi': None, 'original': ref_text
    }
    result['doi'] = extract_doi(ref_text)
    ref_text = re.sub(r'^\s*\d+\.\s*', '', ref_text)

    # 先檢查是否有 URL 後接日期的模式
    url_with_date = re.search(r'(https?://[^\s。)）]+)\s*[（(]\s*(\d{4})\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日\s*[)）]', ref_text)
    
    if url_with_date:
        # 提取內容（「取自」之前）
        if '取自' in ref_text:
            content_part = ref_text[:ref_text.find('取自')].strip().rstrip('。. ')
        else:
            content_part = ref_text[:url_with_date.start()].strip().rstrip('。. ')
        
        # 判斷是標題還是作者（網站名稱）
        # 如果內容中有「。」分隔，前面是作者，後面是標題
        if '。' in content_part:
            parts = content_part.split('。', 1)
            result['authors'] = [parts[0].strip()]
            result['title'] = parts[1].strip()
        else:
            # 只有一段文字，判斷為網站名稱（作者）
            result['authors'] = [content_part]
            result['title'] = None
        
        result['year'] = url_with_date.group(2)
        result['url'] = url_with_date.group(1).rstrip('。.')
        
        return result

    # ========== 一般情況：提取 URL 並從 ref_text 中移除 ==========
    url_match = re.search(r'https?://[^\s。]+', ref_text)
    if url_match:
        raw_url = url_match.group(0)
        result['url'] = raw_url.rstrip('。.')
        # 移除 URL 及其前面的「取自」提示詞
        before_url = ref_text[:url_match.start()].strip()
        before_url = re.sub(r'[。.]\s*取自\s*$', '。', before_url)
        before_url = re.sub(r'[。.]\s*(Retrieved from|Available at|Source)\s*$', '.', before_url, flags=re.IGNORECASE)
        ref_text = before_url.rstrip('。. ')

    # ========== 年份提取 ==========
    # 優先匹配「(年月日)」格式（如：2018年1月24日）
    year_match = re.search(r'[（(]\s*(\d{4})\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日\s*[)）]', ref_text)

    # 次要匹配標準「(年)」格式
    if not year_match:
        year_match = re.search(r'[（(]\s*(\d{4}[a-z]?|n\.?d\.?)\s*[)）]', ref_text, re.IGNORECASE)

    if not year_match:
        year_match = re.search(r'(?<=[\u4e00-\u9fa5])([，,。.]\s*(\d{4})\s*(?:年)?)', ref_text)

    if not year_match: 
        special_match = re.search(r'(.+?)[（(](\d{4})\s*年.+?[)）]', ref_text)
        if special_match:
            result['title'] = special_match.group(1).strip()
            result['year'] = special_match.group(2)
            result['authors'] = []
            
            return result
        return result
    
    # ========== 作者提取 ==========
    result['year'] = year_match.group(1)
    author_part = ref_text[:year_match.start()].strip()
    author_part = re.sub(r'(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])', '', author_part)
    
    # 檢查是否為機構作者（無逗號分隔，整串視為單一作者）
    if '，' not in author_part and ',' not in author_part and '、' not in author_part:
        # 機構作者：整串作為單一作者
        result['authors'] = [author_part] if author_part else []
    else:
        # 個人作者：正常分割（支援頓號、中文逗號、英文逗號）
        result['authors'] = parse_chinese_authors(author_part)
    
    # ========== 處理標題與來源 ==========
    rest = ref_text[year_match.end():].strip().lstrip('.。 ')

    # 移除「取自」等提示詞（避免被誤判為期刊名稱）
    rest = re.sub(r'^[。.]\s*取自[：:\s]*', '', rest)
    rest = re.sub(r'^[。.]\s*(Retrieved from|Available at|Source)[：:\s]*', '', rest, flags=re.IGNORECASE)

    meta_match = re.search(
        r'[,，]\s*(\d+)\s*[卷]?\s*(?:[（(]\s*(\d+)\s*[)）期]?)?\s*[,，。]\s*(\d+)\s*[–\-~]\s*(\d+)',
        rest
    )
    if meta_match:
        result['volume'] = meta_match.group(1)
        if meta_match.group(2):
            result['issue'] = meta_match.group(2)
        result['pages'] = f"{meta_match.group(3)}–{meta_match.group(4)}"
        rest = rest[:meta_match.start()].strip()
        rest = rest.rstrip(',，。. ')
    else:
        vol_match = re.search(r'[,，]\s*(\d+)\s*[卷]', rest)
        if vol_match:
            result['volume'] = vol_match.group(1)
            rest = rest[:vol_match.start()].strip().rstrip(',，。. ')

    match_book = re.search(r'《([^》]+)》', rest)
    match_article = re.search(r'〈([^〉]+)〉', rest)
    
    if match_article:
        result['title'] = match_article.group(1)
        if match_book: result['source'] = match_book.group(1)
    elif match_book:
        pre_book = rest[:match_book.start()].strip()
        if pre_book:
            result['title'] = pre_book.rstrip('。. ')
            result['source'] = match_book.group(1)
        else:
            result['title'] = match_book.group(1)
    else:
        match = re.search(r'。', rest)
        if match:
            result['title'] = rest[:match.start()].strip()
            result['source'] = rest[match.end():].strip().lstrip('。.,，. ').rstrip(',，。. ')
        else:
            match_en = re.search(r'(?<!\d)\.(?!\d)', rest)
            if match_en:
                result['title'] = rest[:match_en.start()].strip()
                result['source'] = rest[match_en.end():].strip().lstrip('。.,，. ').rstrip(',，。. ')
            else:
                result['title'] = rest.strip()

    return result

def extract_numbered_zh_detailed(ref_text):
    result = {
        'format': 'Numbered (ZH)', 'lang': 'ZH',
        'ref_number': None, 'authors': [], 'year': None, 'title': None, 'source': None,
        'doi': None, 'original': ref_text
    }
    result['doi'] = extract_doi(ref_text)
    num_match = re.match(r'^\s*[\[【]\s*(\d+)\s*[\]】]', ref_text)
    if num_match:
        result['ref_number'] = num_match.group(1)
        rest = ref_text[num_match.end():].strip()
    else:
        rest = ref_text
    year_match = re.search(r'\b(\d{4})\b', rest)
    if year_match: result['year'] = year_match.group(1)
    
    match_book = re.search(r'《([^》]+)》', rest)
    if match_book:
        result['source'] = match_book.group(1)
        pre = rest[:match_book.start()]
        parts = re.split(r'[，,]', pre)
        if len(parts) > 0: result['authors'] = parse_chinese_authors(parts[0])
        if len(parts) > 1: result['title'] = parts[1]
    else:
        parts = re.split(r'[，,。.]', rest)
        parts = [p.strip() for p in parts if p.strip()]
        if len(parts) > 0: result['authors'] = parse_chinese_authors(parts[0])
        if len(parts) > 1: result['title'] = parts[1]
        if len(parts) > 2: result['source'] = parts[2]

    return result
