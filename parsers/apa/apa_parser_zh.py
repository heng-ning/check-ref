import re
from utils.text_processor import extract_doi

def parse_chinese_authors(author_str):
    if not author_str: return []
    clean_str = re.sub(r'\s*(等|著|編)$', '', author_str)
    return re.split(r'[、，,]', clean_str)

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

    url_match = re.search(r'https?://[^\s。]+', ref_text)
    if url_match:
        raw_url = url_match.group(0)
        result['url'] = raw_url.rstrip('。.')
        ref_text = ref_text[:url_match.start()].strip().rstrip('。. ')

   # year_match = re.search(r'[（(]\s*(\d{2,4})\s*[)）]', ref_text)
    year_match = re.search(r'[（(]\s*(\d{4}[a-z]?|n\.?d\.?)\s*[)）]', ref_text, re.IGNORECASE)
    if not year_match:
       year_match = re.search(r'(?<=[\u4e00-\u9fa5])([，,。.]\s*(\d{4})\s*(?:年)?)', ref_text)
    if not year_match: 
        special_match = re.search(r'(.+?)[（(](\d{4})\s*年.+?[)）]', ref_text)
        if special_match:
            result['title'] = special_match.group(1).strip()
            result['year'] = special_match.group(2)
            result['authors'] = []
            
            url_match = re.search(r'https?://[^\s]+', ref_text)
            if url_match:
                result['url'] = url_match.group(0).rstrip('。.')
            return result
        return result
    
    result['year'] = year_match.group(1)
    author_part = ref_text[:year_match.start()].strip()
    author_part = re.sub(r'(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])', '', author_part)
    result['authors'] = parse_chinese_authors(author_part)
    
    rest = ref_text[year_match.end():].strip().lstrip('.。 ')

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
