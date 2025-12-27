import re
from utils.text_processor import (
    extract_doi
)

def parse_apa_authors_en(author_str):
    if not author_str: return []
    
    # 先移除 'et al.' (包含 et al, et al., et al)
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
        'proceedings_title': None,
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
        # 移除 DOI（支援斷行情況）
        content_part = re.sub(r'(?:doi:|DOI:|https?://doi\.org/)\s*10\.\d{4,}/[^\s。]+', '', content_part)
        # 清理 DOI 斷行造成的殘留片段（如 "5887-2"）
        content_part = re.sub(r'\s+\d+[\-–]\d+\s*$', '', content_part)
        content_part = content_part.strip()
        
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
        r',\s*(\d+(?:[\–\-]\d+)?)(?:\s*\(([^)]+)\))?(?:,\s*(Article\s+\d+|[A-Za-z]?\d+(?:[\–\-]\s*[A-Za-z]?\d+)?))?(?:\.|\s|$)', 
        content_part
    )

    if meta_match:
        volume_val = meta_match.group(1)
        # 處理卷號範圍（如 7-8）
        if '–' in volume_val or '-' in volume_val:
            result['volume'] = volume_val
        else:
            result['volume'] = volume_val
        
        result['issue'] = meta_match.group(2) if meta_match.group(2) else None
        pages_or_article = meta_match.group(3)
        
        if pages_or_article and pages_or_article.strip():
            # 優先判斷 Article Number
            if pages_or_article.startswith('Article '):
                result['article_number'] = pages_or_article
            elif '-' in pages_or_article or '–' in pages_or_article:
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
        title_source_part = title_source_part.rstrip(',，。. ') # 移除尾部標點
    else:
        pp_match = re.search(r',?\s*pp?\.?\s*([A-Za-z]?\d+[\–\-]\s*[A-Za-z]?\d+)(?:\.)?$', content_part)
        if pp_match:
            result['pages'] = pp_match.group(1)
            title_source_part = content_part[:pp_match.start()].strip()
        else:
            # 移除 DOI/URL 後的內容作為 title_source_part
            title_source_part = content_part
            
            # 如果有 DOI，移除它
            if result.get('doi'):
                title_source_part = re.sub(
                    r'(?:doi:|DOI:|https?://doi\.org/)\s*10\.\d{4,}/[^\s。]+.*$',
                    '',
                    title_source_part
                ).strip()
            
            # 如果有 URL，移除它
            if result.get('url'):
                title_source_part = re.sub(
                    r'https?://[^\s]+.*$',
                    '',
                    title_source_part
                ).strip()

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

        # 處理會議論文集格式（In ... (pp. ...))
        proceedings_match = re.search(
            r'^(.+?)\.\s+In\s+(.+?)\s*\(pp\.\s*([\d\s\–\-—]+)\)',
            title_source_part,
            re.IGNORECASE
        )
        
        if proceedings_match:
            result['title'] = proceedings_match.group(1).strip()
            result['proceedings_title'] = proceedings_match.group(2).strip()
            result['pages'] = re.sub(r'\s+', '', proceedings_match.group(3).strip())
            result['source_type'] = 'Conference Paper'
            
            # 處理後續的出版社資訊
            after_proceedings = title_source_part[proceedings_match.end():].strip().lstrip('. ').strip()
            if after_proceedings:
                # 移除開頭的句號和空格
                after_proceedings = re.sub(r'^\.\s*', '', after_proceedings)
                result['publisher'] = after_proceedings.rstrip('.')
        else:
            # 不是會議論文，進行標題與期刊分割
            # 優先尋找「. 大寫字母」作為標題與期刊的分界
            split_match = re.search(r'\.\s+([A-Z])', title_source_part)
            if split_match:
                split_pos = split_match.start()
                result['title'] = title_source_part[:split_pos].strip()
                result['source'] = title_source_part[split_match.end() - 1:].strip().rstrip('.')
            else:
                # 若找不到明確分界，整串視為標題
                if not title_source_part.startswith('http'):
                    result['title'] = title_source_part.rstrip('.')
            
            # 如果 source 中仍然包含卷期頁碼模式，則移除
            if result.get('source') and result.get('volume'):
                result['source'] = re.sub(
                    r',\s*\d+\s*(?:\([^)]+\))?\s*(?:,\s*[A-Za-z]?\d+(?:[\–\-]\s*[A-Za-z]?\d+)?)?$',
                    '',
                    result['source']
                ).strip()

    text_fields = ['title', 'source', 'publisher', 'editors', 'book_title', 'proceedings_title', 'journal_name', 'conference_name']
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
