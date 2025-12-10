def format_pages_display(pages):
    """格式化頁碼顯示：如果包含字母就不加 pp."""
    if not pages:
        return None
    if re.search(r'[A-Za-z]', pages):
        return pages  # S27–S31
    else:
        return f"pp. {pages}"  # pp. 123-456

# ===== 英文 APA =====
def parse_apa_authors_en(author_str):
    if not author_str: return []
    
    # 先處理 & 或 and（APA 最後一個作者前的連接詞）
    # 將 & 或 and 替換成逗號，統一處理
    clean_str = re.sub(r'\s*,?\s*(&|and)\s+', ', ', author_str, flags=re.IGNORECASE)
    
    # 用「., 」（點號+逗號+空格）來分割作者
    # 這樣可以正確處理 "Last, F. M., Next, A."
    segments = re.split(r'\.\s*,\s*', clean_str)
    
    authors = []
    for seg in segments:
        seg = seg.strip()
        if not seg: continue
        
        # 移除結尾的點號（如果有）
        seg = seg.rstrip('.')
        
        if ',' in seg:
            # 格式：Last, F. M.
            parts = seg.split(',', 1)
            last = parts[0].strip()
            first = parts[1].strip()
            # 確保 first name 有點號結尾
            if first and not first.endswith('.'):
                first += '.'
            authors.append({'last': last, 'first': first})
        else:
            # 只有姓氏
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
        'source_type': None,
        'document_type': None,
        'url': None,
        'doi': None, 'original': ref_text
    }

    # 先提取 DOI 和 URL (提前處理，避免干擾標題解析)
    result['doi'] = extract_doi(ref_text)

    # 提取 URL (支援各種格式，包含空格斷行和連字號斷行)
    # 找到 https:// 開頭，然後向後抓取直到遇到明確的結束標記
    url_start = re.search(r'https?://', ref_text)
    if url_start:
        # 從 https:// 開始向後掃描
        start_pos = url_start.start()
        url_text = ref_text[start_pos:]
        
        # 找到 URL 結束的位置（遇到句號+空格、逗號、或文末）
        # 遇到「句號+換行+大寫字母」也視為結束（處理 DOI 斷行問題）
        end_match = re.search(r'(?:\.\s*\n\s*[A-Z]|\.\s+[A-Z]|,\s|$)', url_text)
        if end_match:
            raw_url = url_text[:end_match.start()].strip()
        else:
            raw_url = url_text.strip()
        
        # 清理 URL：
        # 1. 先處理「連字號+空白」-> 保留連字號
        clean_url = re.sub(r'-\s+', '-', raw_url)
        # 2. 移除所有剩餘空白
        clean_url = re.sub(r'\s+', '', clean_url)
        # 3. 移除結尾的句號（如果有）
        clean_url = clean_url.rstrip('.')
        
        result['url'] = clean_url

        # 如果 URL 是 DOI 連結，清空 URL 欄位
        if re.match(r'^https?://doi\.org/', clean_url, re.IGNORECASE):
            result['url'] = None

        # 保留 url_match 供後續使用
        url_match = type('obj', (object,), {'group': lambda self, n: raw_url if n == 0 else None})()
    else:
        url_match = None
    
    year_match = re.search(r'[（(]\s*(\d{4}[a-z]?|n\.d\.)\s*(?:,\s*[A-Za-z]+\.?\s*\d{0,2})?\s*[)）]', ref_text)
    if not year_match: return result
    
    year_group = year_match.group(1)
    result['year'] = year_group if year_group.lower() != 'n.d.' else 'n.d.'

    # 提取完整日期 (Month Day) - 先檢查 group 是否存在
    try:
        date_match = year_match.group(2)
        if date_match:
            result['month'] = date_match
    except IndexError:
        pass  # 沒有月份資訊，跳過
    
    author_part = ref_text[:year_match.start()].strip()
    result['authors'] = author_part
    result['parsed_authors'] = parse_apa_authors_en(author_part)
    
    content_part = ref_text[year_match.end():].strip()
    if content_part.startswith('.'): content_part = content_part[1:].strip()

    # 移除 DOI 和 URL，避免它們被誤判為標題或來源
    if result['doi']:
        content_part = re.sub(r'(?:doi:|DOI:|https?://doi\.org/)\s*10\.\d{4,}/[^\s。]+', '', content_part).strip()

    if result['url']:
        # 移除原始 URL（包含所有可能的空格變體）
        if url_match:
            # 將原始 URL 中的空格變成彈性匹配模式
            original_url_text = url_match.group(0)
            # 將 URL 拆成片段，用 \s* 連接（允許任意空格）
            url_parts = original_url_text.split()
            flexible_pattern = r'\s*'.join(re.escape(part) for part in url_parts)
            content_part = re.sub(flexible_pattern, '', content_part, flags=re.IGNORECASE)
        
        # 也移除清理後的 URL（以防萬一）
        content_part = content_part.replace(result['url'], '')
        
        # 清理殘留的多餘空格和標點
        content_part = re.sub(r'\s+', ' ', content_part).strip()
        content_part = content_part.rstrip('. ')

    # 判斷是否為書籍章節或一般書籍
    # 優先檢查是否為書籍章節格式（In ... (Eds.)）
    is_book_chapter = bool(re.search(r'\bIn\s+.+?\s*\(Eds?\.\)', content_part, re.IGNORECASE))
    # 或是作者為編者，或標題包含書籍關鍵字
    is_book = is_book_chapter or bool(
        re.search(r'\(eds?\.\)', author_part, re.IGNORECASE) or 
        re.search(r'\b(manual|handbook|guide|textbook|encyclopedia|dictionary)\b', content_part, re.IGNORECASE)
    )

    # 提取後設資料 (卷期頁碼/文章編號)
    # 格式 1: Journal, Vol(Issue), pages. 例如：Journal, 14(2), 123-456.
    # 格式 2: Journal, Vol(Issue), article_number. 例如：Journal, 13(11), 6474.
    # 格式 3: Journal, Vol. 例如：Journal, 160.
    meta_match = re.search(
        r',\s*(\d+)(?:\s*\((\d+)\))?(?:,\s*([A-Za-z]?\d+(?:[\–\-][A-Za-z]?\d+)?))?(?:\.|\s|$)', 
        content_part
    )

    if meta_match:
        result['volume'] = meta_match.group(1)
        result['issue'] = meta_match.group(2) if meta_match.group(2) else None
        pages_or_article = meta_match.group(3)
        
        # 判斷是頁碼還是文章編號
        if pages_or_article and pages_or_article.strip():
            # 如果包含連字號（- 或 –），一定是頁碼
            if '-' in pages_or_article or '–' in pages_or_article:
                result['pages'] = pages_or_article
            else:
                # 純數字或帶字母前綴的數字，判斷是文章編號還是頁碼
                # 邏輯：4 位數以上通常是文章編號（如 6474），3 位數以下可能是頁碼
                if pages_or_article.isdigit():
                    if len(pages_or_article) >= 4:  # 4 位數以上 → 文章編號
                        result['article_number'] = pages_or_article
                    else:  # 3 位數以下 → 可能是單頁頁碼
                        result['pages'] = pages_or_article
                else:
                    # 帶字母的（如 S27）→ 可能是頁碼或文章編號
                    # 簡單判斷：帶字母的短數字視為頁碼
                    if len(pages_or_article) <= 4:
                        result['pages'] = pages_or_article
                    else:
                        result['article_number'] = pages_or_article
        
        title_source_part = content_part[:meta_match.start()].strip()
    else:
        # 格式 2: 傳統頁碼格式 pp. 123-456 或 pp. S27–S31
        pp_match = re.search(r',?\s*pp?\.?\s*([A-Za-z]?\d+[\–\-][A-Za-z]?\d+)(?:\.)?$', content_part)
        if pp_match:
            result['pages'] = pp_match.group(1)
            title_source_part = content_part[:pp_match.start()].strip()
        else:
            title_source_part = content_part

    # 改進標題與來源分割邏輯
    if is_book:
        # === 先檢查是否為書籍章節格式 ===
        # 格式：章節標題. In 編者 (Eds.), 書名 (pp. xxx). 出版社.
        # 改進正則表達式，更精確匹配
        chapter_match = re.search(
            r'^(.+?)\.\s+In\s+(.+?)\s*\(Eds?\.\),\s*(.+?)\s*\(pp\.\s*([\d\s\–\-—]+)\)', 
            title_source_part, 
            re.IGNORECASE
        )

        if chapter_match:
            # 這是書籍章節
            result['title'] = chapter_match.group(1).strip()  # 章節標題
            result['editors'] = "In " + chapter_match.group(2).strip() + " (Eds.)"  # 編者
            result['book_title'] = chapter_match.group(3).strip()  # 書名
            
            # 清理頁碼中的多餘空格
            raw_pages = chapter_match.group(4).strip()
            clean_pages = re.sub(r'\s+', '', raw_pages)  # 移除所有空格
            result['pages'] = clean_pages  # 例如 "254–257"
            
            # 出版社在括號後面
            after_chapter = title_source_part[chapter_match.end():].strip()
            # 移除開頭的句點和空格
            after_chapter = after_chapter.lstrip('. ').strip()
            if after_chapter:
                # 移除結尾的句點
                result['publisher'] = after_chapter.rstrip('.')
            
            result['source_type'] = 'Book Chapter'
        else:
            # 一般書籍格式：標題. 出版社.
            split_match = re.search(r'\.\s+([A-Z])', title_source_part)
            
            if split_match:
                split_pos = split_match.start()
                result['title'] = title_source_part[:split_pos].strip()
                
                # 出版社部分
                publisher_part = title_source_part[split_pos + 1:].strip()
                next_dot = publisher_part.find('.')
                if next_dot != -1:
                    result['publisher'] = publisher_part[:next_dot].strip()
                else:
                    result['publisher'] = publisher_part.rstrip('.')
            else:
                result['title'] = title_source_part.rstrip('.')
    else:
        # 期刊格式：標題. 期刊名
        # 先識別並移除文獻類型標註 (如 [Project Report], Technical Report 等)
        document_type_pattern = r'\.\s*(\[?(?:Project|Technical|Research|Working|Conference|Discussion)\s+(?:Report|Paper|Brief)\]?)\.'
        doc_type_match = re.search(document_type_pattern, title_source_part, re.IGNORECASE)
        
        if doc_type_match:
            # 提取文獻類型
            result['document_type'] = doc_type_match.group(1).strip('[]')
            
            # 從 title_source_part 中移除文獻類型
            title_source_part = (
                title_source_part[:doc_type_match.start()] + 
                '. ' + 
                title_source_part[doc_type_match.end():]
            ).strip()
        
        # 原本的標題與來源分割邏輯
        split_index = title_source_part.rfind('. ')
        if split_index != -1:
            result['title'] = title_source_part[:split_index].strip()
            result['source'] = title_source_part[split_index + 1:].strip().rstrip('.')
        else:
            if not title_source_part.startswith('http'):
                result['title'] = title_source_part.rstrip('.')

    # 清理所有文字欄位中的斷行連字號
    text_fields = ['title', 'source', 'publisher', 'editors', 'book_title', 'journal_name', 'conference_name']
    for field in text_fields:
        if result.get(field) and isinstance(result[field], str):
            # 移除單字中的斷行連字號（如 "perform- ance" -> "performance"）
            # 模式1: 連字號+空格+小寫字母
            result[field] = re.sub(r'-\s+([a-z])', r'\1', result[field])
            # 模式2: 單純的連字號+空格（備用）
            result[field] = re.sub(r'-\s+', '', result[field])

    return result

# ===== 中文 APA =====
def parse_chinese_authors(author_str):
    if not author_str: return []
    clean_str = re.sub(r'\s*(等|著|編)$', '', author_str)
    return re.split(r'[、，,]', clean_str)

def extract_apa_zh_detailed(ref_text):
    result = {
        'format': 'APA (ZH)', 'lang': 'ZH',
        'authors': [], 'year': None, 'title': None, 'source': None,
        'volume': None, 'issue': None, 'pages': None,
        'doi': None, 'original': ref_text
    }
    result['doi'] = extract_doi(ref_text)
    year_match = re.search(r'[（(]\s*(\d{2,4})\s*[)）]', ref_text)
    if not year_match: return result
    
    result['year'] = year_match.group(1)
    author_part = ref_text[:year_match.start()].strip()
    result['authors'] = parse_chinese_authors(author_part)
    
    rest = ref_text[year_match.end():].strip().lstrip('.。 ')
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
        # [UPDATED] 增加後備方案，如果沒有書名號，嘗試用句號分隔抓取來源
        parts = re.split(r'[。.]', rest)
        # 過濾空字串
        parts = [p.strip() for p in parts if p.strip()]
        if len(parts) > 0: result['title'] = parts[0]
        if len(parts) > 1: result['source'] = parts[1] # 嘗試抓取來源
            
    vol_match = re.search(r'(\d+)\s*[卷]', rest)
    if vol_match: result['volume'] = vol_match.group(1)
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
        # 嘗試抓作者和篇名
        parts = re.split(r'[，,]', pre)
        if len(parts) > 0: result['authors'] = parse_chinese_authors(parts[0])
        if len(parts) > 1: result['title'] = parts[1]
    else:
        # [UPDATED] 增加後備方案，嘗試抓取來源 (假設結構: 作者, 篇名, 來源)
        parts = re.split(r'[，,。.]', rest)
        parts = [p.strip() for p in parts if p.strip()]
        if len(parts) > 0: result['authors'] = parse_chinese_authors(parts[0])
        if len(parts) > 1: result['title'] = parts[1]
        if len(parts) > 2: result['source'] = parts[2] # 嘗試抓取來源

    return result

# ===== APA 斷行合併（混合模式）=====
def find_apa_head(ref_text):
    """[NEW] 偵測 APA 格式開頭 (年份) - 取代舊的 find_apa"""
    # 英文 APA: Author (2020).
    # 中文 APA: 作者 (2020)。
    match = re.search(r'[（(]\s*(\d{4}(?:[a-z])?|n\.d\.)\s*(?:,\s*([A-Za-z]+\.?\s*\d{0,2}))?\s*[)）]', ref_text)
    if not match: return False
    
    # 確保年份括號出現在前面 (例如前 50 個字內，避免誤判文中的年份)
    if match.start() > 80: return False 
    
    return True

def is_reference_head_unified(para):
    """
    [UPDATED] [APA/混合模式] 判斷一行文字是否為新文獻
    """
    para = normalize_text(para)

    # DOI 特徵：數字開頭 + 斜線 + 字母數字混合
    if re.match(r'^\d{4,}/[a-z0-9\.\-/]+', para, re.IGNORECASE):
        return False
    if re.match(r'^[a-z0-9]+\-[a-z]{2}$', para, re.IGNORECASE):
        return False
    
    # 0. ✅ 強特徵白名單：明確的新文獻開頭（優先級最高）
    
    # A. 編號格式 [1]
    if re.match(r'^\s*[\[【]\s*\d+\s*[】\]]', para):
        return True
    
    # B. 標準 APA 作者格式：Last, F. 開頭
    # 只要開頭是 "姓, 名縮寫"，且不是小寫或數字開頭，就很可能是新文獻
    # 不管年份在哪（可能被斷行到下一段）
    author_start = re.match(r'^([A-Z][A-Za-z\-\']+),\s+([A-Z]\.(?:\s*[A-Z]\.)*)', para)
    
    # C. 組織作者格式：開頭大寫單字 + (縮寫) + 年份
    # 例如：World Health Organization (WHO). (2020)
    org_author_match = re.match(
        r'^[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*\s*\([A-Z]+\)\.\s*\((\d{4})', 
        para
    )
    if org_author_match:
        year = org_author_match.group(1)
        if is_valid_year(year):
            return True

    # D. 一般組織作者（沒有縮寫）：開頭多個大寫單字 + 年份
    # 例如：National Research Council. (2019)
    org_simple_match = re.match(
        r'^[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){2,}\.\s*\((\d{4})', 
        para
    )
    if org_simple_match:
        year = org_simple_match.group(1)
        if is_valid_year(year):
            return True

    if author_start:
        # 進一步驗證：排除明顯不是作者的情況
        # 1. 後面不能直接接小寫字母（表示是句子中間）
        after_author = para[author_start.end():].strip()
        if after_author and after_author[0].islower():
            pass  # 可能是句子，不處理
        else:
            # 2. 檢查是否有合理的後續內容（逗號、&、or、年份括號）
            if re.match(r'^[,&\(]', after_author) or not after_author:
                return True
            # 3. 如果後面還有其他作者名（說明是作者列表開頭）
            if re.search(r'[,&]\s+[A-Z][a-z]+,\s+[A-Z]\.', after_author[:50]):
                return True
            # 4. 如果是 DOI/URL 結尾後的新作者
            # 檢查：作者格式完整 + 後面有年份 → 這是新文獻
            if re.search(r'\(\d{4}\)', para):
                return True
    
    # 1. 🚫 黑名單：絕對不是新文獻的情況
    
    # A. 網址保護
    if re.search(r'(https?://|doi\.org|doi:|www\.)', para, re.IGNORECASE):
        url_only = re.sub(r'https?://[^\s]+', '', para).strip()
        if len(url_only) < 10:
            return False
        if not (re.match(r'^\s*[\[【]', para) or author_start):
            return False
            
    # B. 月份/日期保護
    if re.match(r'^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*\d{4}', para, re.IGNORECASE):
        return False
        
    # C. 卷期頁碼保護
    if re.match(r'^(Vol\.|No\.|pp\.|p\.|Page)', para, re.IGNORECASE):
        return False
        
    # D. 小寫開頭保護
    if re.match(r'^[a-z]', para):
        return False
    
    # E. 作者列表延續保護（只有 & 或逗號+名字，沒有姓氏開頭）
    # 例如：", & Varatharajan, S." 這種不算新文獻開頭
    if re.match(r'^[,&]\s', para):
        return False

    # 如果開頭是縮寫（如 "A., Malhotra"），但後面沒有年份括號 (20XX)
    # 這是作者列表延續，不是新文獻開頭
    # 例如："A., Malhotra, R. K., & Martin, J. L." (沒有年份)
    if re.match(r'^[A-Z]\.(?:\s*[A-Z]\.)*\s*,', para):
        # 檢查這一段是否有年份括號 (19XX) 或 (20XX)
        # 如果沒有年份，這肯定是作者列表延續
        if not re.search(r'[（(]\s*(?:19|20)\d{2}', para):
            return False

    # 2. ✅ 其他白名單特徵
    
    # C. APA 標準格式 (Year) - 年份在括號內
    if find_apa_head(para):
        return True
        
    # D. 類 APA (Year in dots)
    year_match = re.search(r'[\.,]\s*(19|20)\d{2}[a-z]?[\.,]', para[:80])
    if year_match:
        pre_text = para[:year_match.start()].strip()
        if len(pre_text) > 3:
            if not has_chinese(para):
                if ',' in pre_text or '.' in pre_text:
                    return True
            else:
                return True

    return False

def merge_references_unified(paragraphs):
    """[UPDATED from test1204-6] [APA/混合模式] 合併斷行"""
    merged = []
    current_ref = ""
    
    for i, para in enumerate(paragraphs):
        para = para.strip()
        if not para: continue
        
        # 排除純數字頁碼 (長度短且無連字號)
        if para.isdigit() and len(para) < 4: continue

        # 排除頁首/頁尾文字
        # 特徵：全大寫、長度短、沒有年份括號、沒有編號
        if para.isupper() and len(para) < 50:
            # 1. 包含 ET AL 的作者頁首
            if 'ET AL' in para:
                continue
            # 2. 縮寫開頭的頁首（如 "S. JAYDARIFARD ET AL."）
            if re.match(r'^[A-Z]\.\s+[A-Z]+', para):
                continue
            # 3. 期刊名稱或章節標題的頁首（如 "TRANSPORT REVIEWS"）
            # 排除條件：全大寫 + 沒有數字 + 沒有括號 + 沒有標點（除了空格）
            if not re.search(r'[\d\(\)\[\]\.,:;]', para):
                continue  # 跳過這行
        
        is_new_ref = is_reference_head_unified(para)

        # 特殊判斷：如果當前文獻以 & 或 , 結尾（表示作者列表未完成）
        # 且這行開頭是作者名+年份，這行應該是作者列表的最後一位，不是新文獻
        if is_new_ref and current_ref:
            # 檢查上一行結尾
            current_ref_stripped = current_ref.rstrip()
            if current_ref_stripped.endswith('&') or current_ref_stripped.endswith(','):
                # 檢查這行是否為：作者名 + 年份（作者列表最後一位的模式）
                # 例如：Varatharajan, S. (2019). ...
                if re.match(r'^[A-Z][A-Za-z\-\']+,\s+[A-Z]\.\s*[（(]', para):
                    # 這是作者列表的最後一位，應該合併
                    is_new_ref = False

        # 如果當前累積的文獻沒有年份，且新段落有年份
        # 那新段落應該是當前文獻的延續，不是新文獻
        if is_new_ref and current_ref:
            # 檢查 current_ref 是否有年份
            has_year_in_current = bool(re.search(r'[（(]\s*(?:19|20)\d{2}', current_ref))
            # 檢查 para 是否有年份
            has_year_in_para = bool(re.search(r'[（(]\s*(?:19|20)\d{2}', para))
            
            # 如果當前文獻沒年份，但新段落有年份 → 新段落是延續
            if not has_year_in_current and has_year_in_para:
                is_new_ref = False
        
        # 如果當前累積的文獻以 DOI 或完整 URL 結尾且新段落是明確的作者開頭，強制切分
        if current_ref and not is_new_ref:
            current_stripped = current_ref.rstrip()
            # 檢查是否以 DOI 或 URL 結尾
            ends_with_doi_url = bool(
                re.search(r'(https?://[^\s]+|doi\.org/[^\s]+|10\.\d{4}/[^\s]+)[.\s]*$', current_stripped)
            )
            
            # 檢查新段落是否為明確的作者開頭
            clear_author_start = bool(
                re.match(r'^([A-Z][A-Za-z\-\']+),\s+([A-Z]\.(?:\s*[A-Z]\.)*)', para) and
                re.search(r'\(\d{4}\)', para)
            )
            
            # 如果兩個條件都滿足，強制切分
            if ends_with_doi_url and clear_author_start:
                is_new_ref = True

        if is_new_ref:
            if current_ref:
                merged.append(current_ref)
            current_ref = para
        else:
            if current_ref:
                if has_chinese(current_ref[-1:]) and has_chinese(para[:1]):
                    current_ref += "" + para
                elif current_ref.endswith('-'):
                    # 判斷是否為單字斷行
                    if para and para[0].islower():
                        current_ref = current_ref[:-1] + para
                    else:
                        current_ref = current_ref + " " + para
                # 處理頁碼斷行：連字號+空格+數字
                elif re.search(r'[\–\-—]\s*$', current_ref) and para and para[0].isdigit():
                    current_ref = current_ref.rstrip() + para
                # 處理 DOI 斷行
                elif re.search(r'doi\.org/[^\s]+\.$', current_ref, re.IGNORECASE) and para and para[0].isdigit():
                    current_ref = current_ref + para  # DOI 直接連接
                # 處理一般 URL 結尾是句點的斷行
                elif re.search(r'https?://[^\s]+\.$', current_ref) and para and not para[0].isupper():
                    current_ref = current_ref + para
                else:
                    current_ref += " " + para
            else:
                current_ref = para
            
    if current_ref: 
        merged.append(current_ref)
    
    return merged

# ===== APA 格式轉換 =====
def convert_en_apa_to_ieee(data):
    ieee_authors = []
    for auth in data.get('parsed_authors', []):
        ieee_authors.append(f"{auth['first']} {auth['last']}".strip())
    auth_str = ", ".join(ieee_authors)
    if len(ieee_authors) > 2: auth_str = re.sub(r', ([^,]+)$', r', and \1', auth_str)
    
    parts = []
    if auth_str: parts.append(auth_str + ",")
    if data.get('title'): parts.append(f'"{data["title"]},"')
    
    # 分別處理期刊和書籍
    if data.get('source'):  # 期刊
        parts.append(f"{data['source']},")
    elif data.get('publisher'):  # 書籍
        parts.append(f"{data['publisher']},")
    
    if data.get('volume'): parts.append(f"vol. {data['volume']},")
    if data.get('issue'): parts.append(f"no. {data['issue']},")
    if data.get('pages'): parts.append(f"pp. {data['pages']},")
    
    # 加入月份
    if data.get('month'): parts.append(f"{data['month']}")
    if data.get('year'): parts.append(f"{data['year']}.")
    
    # 加入 DOI 或 URL
    if data.get('doi'): parts.append(f"doi: {data['doi']}.")
    elif data.get('url'): parts.append(f"[Online]. Available: {data['url']}")
    
    return " ".join(parts)

def convert_zh_apa_to_num(data):
    parts = []
    # [UPDATED] 修正作者連接符號，list 轉字串
    if isinstance(data.get('authors'), list):
        auth = "、".join(data.get('authors'))
    else:
        auth = data.get('authors', '')
        
    if auth: parts.append(auth)
    if data.get('title'): parts.append(f"「{data['title']}」")
    # [UPDATED] 確保出處有被抓到才顯示
    if data.get('source'): parts.append(f"《{data['source']}》")
    if data.get('year'): parts.append(data['year'])
    return "，".join(parts) + "。"

def convert_zh_num_to_apa(data):
    # [UPDATED] 修正作者連接符號
    if isinstance(data.get('authors'), list):
        auth = "、".join(data.get('authors'))
    else:
        auth = data.get('authors', '')
        
    parts = []
    parts.append(f"{auth}（{data.get('year', '無年份')}）")
    if data.get('title'): parts.append(data['title'])
    if data.get('source'): parts.append(f"《{data['source']}》")
    return "。".join(parts) + "。"

# ===== 核心整合 =====
def process_single_reference(ref_text):
    """
    [Updated] 核心分流邏輯
    策略：優先判斷是否為編號格式 ([1]...), 若是則一律交給 IEEE 模組 (中英文通用)。
    """
    ref_text = normalize_text(ref_text)
    
    # 1. 優先判斷：是否為編號格式 ([1], [2], 【1】...)
    # 只要是編號開頭，不管中英文，全部視為 IEEE 格式
    if re.match(r'^\s*[\[【]', ref_text):
        # 呼叫您剛剛更新過、中英文通吃的 IEEE 解析器
        data = extract_ieee_reference_full(ref_text)
        # 這個解析器回傳的 data['format'] 預設就是 'IEEE'
        
    else:
        # 2. 非編號格式 (APA 類)，再根據語言分流
        if has_chinese(ref_text):
            data = extract_apa_zh_detailed(ref_text)
        else:
            data = extract_apa_en_detailed(ref_text)
            
    # [關鍵整合]：確保回傳的字典包含比對邏輯所需的 'author' 欄位
    if isinstance(data.get('authors'), list):
        data['author'] = " ".join(data['authors']) 
    elif isinstance(data.get('authors'), str):
        data['author'] = data['authors']
    else:
        data['author'] = "Unknown"
        
    return data


# 引入：
import re
from common_utils import (
    normalize_text,
    has_chinese,
    extract_doi,
    is_valid_year
)
from ieee_module import extract_ieee_reference_full