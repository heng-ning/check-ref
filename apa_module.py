# apa_module.py
import re
from common_utils import (
    normalize_text,
    has_chinese,
    extract_doi,
    is_valid_year,
)

# =============================================================================
# 共用工具
# =============================================================================

def format_pages_display(pages):
    """格式化頁碼顯示：如果包含字母就不加 pp."""
    if not pages:
        return None
    if re.search(r'[A-Za-z]', pages):
        return pages  # S27–S31
    else:
        return f"pp. {pages}"  # pp. 123-456

# =============================================================================
# 英文 APA 解析
# =============================================================================

def parse_apa_authors_en(author_str):
    if not author_str: return []
    
    # [NEW] 先移除 'et al.' (包含 et al, et al., et al)
    author_str = re.sub(r'\s+et\s+al\.?', '', author_str, flags=re.IGNORECASE)
    
    # 先處理 & 或 and
    clean_str = re.sub(r'\s*,?\s*(&|and)\s+', ', ', author_str, flags=re.IGNORECASE)
    
    # 用「., 」分割
    segments = re.split(r'\.\s*,\s*', clean_str)
    
    authors = []
    for seg in segments:
        seg = seg.strip()
        if not seg: continue
        
        seg = seg.rstrip('.')
        
        if ',' in seg:
            parts = seg.split(',', 1)
            last = parts[0].strip()
            first = parts[1].strip()
            if first and not first.endswith('.'):
                first += '.'
            authors.append({'last': last, 'first': first})
        else:
            authors.append({'last': seg, 'first': ''})
    
    return authors

def extract_apa_en_detailed(ref_text):
    result = {
        'format': 'APA (EN)', 'lang': 'EN',
        'authors': "Unknown", 'parsed_authors': [],
        'year': None, 'title': None, 'source': None,
        'volume': None, 'issue': None, 'pages': None,
        'article_number': None,
        'publisher': None,
        'editors': None,
        'book_title': None,
        'edition': None,
        'source_type': None,
        'document_type': None,
        'url': None,
        'doi': None, 'original': ref_text
    }

    result['doi'] = extract_doi(ref_text)

    # 提取 URL
    url_start = re.search(r'https?://', ref_text)
    if url_start:
        start_pos = url_start.start()
        url_text = ref_text[start_pos:]
        
        end_match = re.search(r'(?:\.\s*\n\s*[A-Z]|\.\s+[A-Z]|,\s|$)', url_text)
        if end_match:
            raw_url = url_text[:end_match.start()].strip()
        else:
            raw_url = url_text.strip()
        
        clean_url = re.sub(r'-\s+', '-', raw_url)
        clean_url = re.sub(r'\s+', '', clean_url)
        clean_url = clean_url.rstrip('.')
        
        result['url'] = clean_url

        if re.match(r'^https?://doi\.org/', clean_url, re.IGNORECASE):
            result['url'] = None

        url_match = type('obj', (object,), {'group': lambda self, n: raw_url if n == 0 else None})()
    else:
        url_match = None
    
    # 年份提取
    year_match = re.search(r'[（(]\s*(\d{4}[a-z]?|n\.d\.)\s*(?:,\s*[A-Za-z]+\.?\s*\d{0,2})?\s*[)）]', ref_text)
    
    if not year_match:
        comma_year_match = re.search(r',\s*(\d{4}[a-z]?)\s*[.,]', ref_text)
        if comma_year_match and comma_year_match.start() < 100: 
            year_match = comma_year_match

    if not year_match: return result
    
    year_group = year_match.group(1)
    result['year'] = year_group if year_group.lower() != 'n.d.' else 'n.d.'

    try:
        if year_match.lastindex and year_match.lastindex >= 2:
            date_match = year_match.group(2)
            if date_match:
                result['month'] = date_match
    except IndexError:
        pass 
    
    author_part = ref_text[:year_match.start()].strip()
    author_part = author_part.rstrip(', ')
    
    result['authors'] = author_part
    result['parsed_authors'] = parse_apa_authors_en(author_part)
    
    content_part = ref_text[year_match.end():].strip()
    content_part = content_part.lstrip('., ').strip()

    if result['doi']:
        content_part = re.sub(r'(?:doi:|DOI:|https?://doi\.org/)\s*10\.\d{4,}/[^\s。]+', '', content_part).strip()

    if result['url']:
        if url_match:
            original_url_text = url_match.group(0)
            url_parts = original_url_text.split()
            flexible_pattern = r'\s*'.join(re.escape(part) for part in url_parts)
            content_part = re.sub(flexible_pattern, '', content_part, flags=re.IGNORECASE)
        
        content_part = content_part.replace(result['url'], '')
        content_part = re.sub(r'\s+', ' ', content_part).strip()
        content_part = content_part.rstrip('. ')

    is_book_chapter = bool(re.search(r'\bIn\s+.+?\s*\(Eds?\.\)', content_part, re.IGNORECASE))
    is_book = is_book_chapter or bool(
        re.search(r'\(eds?\.\)', author_part, re.IGNORECASE) or 
        re.search(r'\b(manual|handbook|guide|textbook|encyclopedia|dictionary)\b', content_part, re.IGNORECASE)
    )

    if not is_book:
        has_volume_issue = bool(re.search(r',\s*\d+\s*[\(（]', content_part))
        has_volume_pages = bool(re.search(r',\s*\d+\s*,\s*[A-Z]?\d+', content_part))
        
        if not (has_volume_issue or has_volume_pages):
            well_known_publishers = r'\b(Wiley|Springer|Elsevier|Sage|Routledge|Pearson|McGraw|Oxford|Cambridge|Freeman|Jossey|Bass|Guilford|Palgrave|Macmillan|Penguin|Random|Simon|Schuster|HarperCollins|Norton|Houghton|Mifflin|Addison|Wesley)\b'
            if re.search(well_known_publishers, content_part, re.IGNORECASE):
                is_book = True
            elif re.search(r'\b(Press|Publisher|Publishing|Books|University|College|Institute|Foundation|Association|Inc\.|Ltd\.|LLC|Co\.|Group)\b', content_part, re.IGNORECASE):
                is_book = True
            else:
                sentence_splits = list(re.finditer(r'\.\s+[A-Z]', content_part))
                has_comma_with_numbers = bool(re.search(r',\s*\d+', content_part))
                
                if len(sentence_splits) == 1 and not has_comma_with_numbers:
                    last_part = content_part[sentence_splits[0].end()-1:].strip()
                    if not re.search(r'\b(Journal|Review|Magazine|Quarterly|Bulletin|Proceedings|Transactions|Annals)\b', last_part, re.IGNORECASE):
                        if re.match(r'^(?:[A-Z]\.\s+)*[A-Z][A-Za-z\-&]+(?:\s+[A-Z][A-Za-z\-&]+)*\.?\s*$', last_part):
                            is_book = True

    meta_match = re.search(
        r',\s*(\d+)(?:\s*\(([^)]+)\))?(?:,\s*([A-Za-z]?\d+(?:[\–\-][A-Za-z]?\d+)?))?(?:\.|\s|$)', 
        content_part
    )

    if meta_match:
        result['volume'] = meta_match.group(1)
        result['issue'] = meta_match.group(2) if meta_match.group(2) else None
        pages_or_article = meta_match.group(3)
        
        if pages_or_article and pages_or_article.strip():
            if '-' in pages_or_article or '–' in pages_or_article:
                result['pages'] = pages_or_article
            else:
                if pages_or_article.isdigit():
                    if len(pages_or_article) >= 4:
                        result['article_number'] = pages_or_article
                    else:
                        result['pages'] = pages_or_article
                else:
                    if len(pages_or_article) <= 4:
                        result['pages'] = pages_or_article
                    else:
                        result['article_number'] = pages_or_article
        
        title_source_part = content_part[:meta_match.start()].strip()
    else:
        pp_match = re.search(r',?\s*pp?\.?\s*([A-Za-z]?\d+[\–\-][A-Za-z]?\d+)(?:\.)?$', content_part)
        if pp_match:
            result['pages'] = pp_match.group(1)
            title_source_part = content_part[:pp_match.start()].strip()
        else:
            title_source_part = content_part

    if is_book:
        chapter_match = re.search(
            r'^(.+?)\.\s+In\s+(.+?)\s*\(Eds?\.\),\s*(.+?)\s*\((?:(\d+(?:st|nd|rd|th)\s+ed\.),?\s*)?pp\.\s*([\d\s\–\-—]+)\)', 
            title_source_part, 
            re.IGNORECASE
        )
        if chapter_match:
            result['title'] = chapter_match.group(1).strip()
            result['editors'] = "In " + chapter_match.group(2).strip() + " (Eds.)"
            result['book_title'] = chapter_match.group(3).strip()
            if chapter_match.group(4):
                result['edition'] = chapter_match.group(4).strip()
            result['pages'] = re.sub(r'\s+', '', chapter_match.group(5).strip())
            
            after_chapter = title_source_part[chapter_match.end():].strip().lstrip('. ').strip()
            if after_chapter:
                result['publisher'] = after_chapter.rstrip('.')
            result['source_type'] = 'Book Chapter'
        else:
            split_match = re.search(r'\.\s+([A-Z])', title_source_part)
            if split_match:
                split_pos = split_match.start()
                result['title'] = title_source_part[:split_pos].strip()
                result['publisher'] = title_source_part[split_match.end() - 1:].strip().rstrip('.')
                
                edition_in_title = re.search(r'\((\d+(?:st|nd|rd|th)\s+ed\.)\)\s*$', result['title'])
                if edition_in_title:
                    result['edition'] = edition_in_title.group(1)
                    result['title'] = result['title'][:edition_in_title.start()].strip()
            else:
                result['title'] = title_source_part.rstrip('.')
                edition_in_title = re.search(r'\((\d+(?:st|nd|rd|th)\s+ed\.)\)\s*$', result['title'])
                if edition_in_title:
                    result['edition'] = edition_in_title.group(1)
                    result['title'] = result['title'][:edition_in_title.start()].strip()
    else:
        document_type_pattern = r'\.\s*(\[?(?:Project|Technical|Research|Working|Conference|Discussion)\s+(?:Report|Paper|Brief)\]?)\.'
        doc_type_match = re.search(document_type_pattern, title_source_part, re.IGNORECASE)
        
        if doc_type_match:
            result['document_type'] = doc_type_match.group(1).strip('[]')
            title_source_part = (
                title_source_part[:doc_type_match.start()] + 
                '. ' + 
                title_source_part[doc_type_match.end():]
            ).strip()
        
        split_index = title_source_part.rfind('. ')
        if split_index != -1:
            result['title'] = title_source_part[:split_index].strip()
            result['source'] = title_source_part[split_index + 1:].strip().rstrip('.')
        else:
            if not title_source_part.startswith('http'):
                result['title'] = title_source_part.rstrip('.')

    text_fields = ['title', 'source', 'publisher', 'editors', 'book_title', 'journal_name', 'conference_name']
    for field in text_fields:
        if result.get(field) and isinstance(result[field], str):
            result[field] = re.sub(r'-\s+([a-z])', r'\1', result[field])
            result[field] = re.sub(r'-\s+', '', result[field])
    
    if result['parsed_authors']:
        result['authors'] = [
            f"{a['last']} {a['first']}".strip()
            for a in result['parsed_authors']
        ]
    return result

# =============================================================================
# 中文 APA 解析
# =============================================================================

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

    year_match = re.search(r'[（(]\s*(\d{2,4})\s*[)）]', ref_text)
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

# =============================================================================
# APA 斷行合併與頭部偵測 (核心修正處)
# =============================================================================

def find_apa_head(ref_text):
    """偵測 APA 格式開頭 (含變體格式)"""
    match = re.search(r'[（(]\s*(\d{4}(?:[a-z])?|n\.d\.)\s*(?:,\s*([A-Za-z]+\.?\s*\d{0,2}))?\s*[)）]', ref_text)
    if match and match.start() < 80: return True
    
    match_comma = re.search(r'[\.,]\s*(\d{4}(?:[a-z])?)\s*[\.,]', ref_text)
    if match_comma and match_comma.start() < 80: return True
    
    return False

def merge_references_unified(paragraphs):
    """
    [UPDATED] 通用合併邏輯：
    1. 過濾分類標題
    2. 判斷新文獻開始 (增加數值大小防呆，避免文章編號 104979. 被誤判)
    3. 判斷延續
    """
    merged = []
    current_ref = ""
    
    for para in paragraphs:
        para = normalize_text(para)
        if not para: continue

        # 1. 過濾分類標題
        category_keywords = r'(Conference|Journal|Article|Preprint|Paper|Book|Theses|Dissertation|Report|Proceedings|Symposium|Web|Online)'
        if re.match(r'^\d+\.\s*' + category_keywords, para, re.IGNORECASE):
            if len(para) < 50:
                continue

        # 2. 判斷是否為新文獻開始 (Priority High)
        is_new_start = False
        
        # A. 中文標準
        if re.match(r'^[\u4e00-\u9fa5]+.*?[\(（]\d{4}[\)）]', para):
            is_new_start = True
            
        # B. 英文標準
        elif re.match(r'^[A-Z][^\d\(\)]+(\(|\,\s*)\d{4}', para) and not re.match(r'^\s*(&|and)\b', para, re.IGNORECASE):
            is_new_start = True
            
        # C. 編號開頭 (修正：避免把文章編號 101599. 誤判為列表編號)
        elif re.match(r'^(\d+)\.', para):
            # 抓出數字
            num_match = re.match(r'^(\d+)', para)
            num_val = int(num_match.group(1))
            
            # [FIX] 防呆條件 1: 數字 > 500 通常是文章編號，不是列表順序
            if num_val > 500:
                is_new_start = False
            # [FIX] 防呆條件 2: 數字後面緊接 DOI 或 URL
            elif re.search(r'^\d+\.\s*(https?://|doi:)', para, re.IGNORECASE):
                is_new_start = False
            else:
                is_new_start = True
        
        # D. IEEE 括號編號 [1]
        elif re.match(r'^\s*[\[【]\s*\d+\s*[】\]]', para):
            is_new_start = True

        # 3. 判斷是否為延續 (Priority Low)
        is_continuation = False
        if not is_new_start:
            # A. 包含 DOI 或 arXiv
            if re.search(r'(doi:10\.|doi\.org|arXiv:)', para, re.IGNORECASE):
                is_continuation = True
            # B. 會議資訊 (全大寫+年份)
            elif re.match(r'^([A-Z]{2,}(?:\s+[A-Z]{2,})*)\s+\d{4}', para):
                is_continuation = True
            # C. 特殊出版資訊
            elif re.match(r'^(Paper No\.|Vol\.|pp\.|no\.)', para, re.IGNORECASE):
                is_continuation = True
            # D. 大數字開頭的行 (如 104979.) 也視為延續
            elif re.match(r'^\d{4,}\.', para):
                is_continuation = True

        # 4. 執行動作
        if is_new_start:
            if current_ref: merged.append(current_ref)
            current_ref = para
        elif is_continuation:
            if current_ref:
                if has_chinese(current_ref[-1:]) and has_chinese(para[:1]):
                    current_ref += para
                else:
                    current_ref += " " + para
            else:
                current_ref = para
        else:
            if current_ref:
                if has_chinese(current_ref[-1:]) and has_chinese(para[:1]):
                    current_ref += para
                elif current_ref.endswith('-'):
                    if para and para[0].islower():
                        current_ref = current_ref[:-1] + para
                    else:
                        current_ref = current_ref + " " + para
                else:
                    current_ref += " " + para
            else:
                current_ref = para
                
    if current_ref: merged.append(current_ref)
    return merged

# =============================================================================
# APA 格式轉換
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
            if data.get('pages'):
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