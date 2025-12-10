import re

# ===== 1. 引入依賴 =====
from common_utils import normalize_chinese_text, has_chinese

# ===== IEEE 作者解析 =====
def parse_ieee_authors(authors_str):
    """
    [Polyglot Version] 支援中英文作者解析
    中文姓名策略：不拆分 First/Last，全部視為 Last Name 以保持全名顯示。
    """
    if not authors_str: return []

    # 1. 預處理：清理 "and", "&", "等"
    clean_str = re.sub(r',?\s+\b(and|&)\b\s+', ',', authors_str, flags=re.IGNORECASE)
    clean_str = re.sub(r'\s+等$', '', clean_str) # 移除中文 "等"
    
    # 2. 分割作者
    # 支援中文頓號 (、) 和逗號
    raw_authors = [a.strip() for a in re.split(r'[,、]', clean_str) if a.strip()]
    
    parsed_list = []
    
    for auth in raw_authors:
        # === 中文姓名處理 ===
        if has_chinese(auth):
            parsed_list.append({'last': auth, 'first': ''})
            continue

        # === 英文姓名處理 (保持原本邏輯) ===
        if ',' in auth:
            parts = auth.split(',', 1)
            parsed_list.append({'last': parts[0].strip(), 'first': parts[1].strip()})
        else:
            parts = auth.split()
            if not parts: continue
            if len(parts) == 1:
                parsed_list.append({'first': '', 'last': parts[0]})
            else:
                last_name = parts[-1]
                first_name = " ".join(parts[:-1])
                first_name = re.sub(r'\band\b', '', first_name, flags=re.IGNORECASE).strip()
                parsed_list.append({'first': first_name, 'last': last_name})
            
    return parsed_list


# ===== IEEE 完整解析 =====
def extract_ieee_reference_full(ref_text):
    """
    [Final Hybrid Version] 
    1. 中文：使用靈活分割邏輯 (支援商周、論文等特殊格式)。
    2. 英文：嚴格保留原始邏輯 (包含 Ethereum, arXiv 等修復)。
    """
    
    # === 0. 基礎預處理 ===
    original_ref_text = ref_text
    # 為了讓 Regex 能處理中文標點，先做標準化
    ref_text = normalize_chinese_text(ref_text)
    
    # 基本欄位初始化
    result = {
        'format': 'IEEE',
        'ref_number': None,
        'source_type': 'Unknown',
        'authors': None,
        'parsed_authors': [],
        'title': None,
        'source': None,
        'journal_name': None,
        'conference_name': None,
        'volume': None,
        'issue': None,
        'pages': None,
        'year': None,
        'month': None,
        'publisher': None,
        'location': None,
        'edition': None,
        'url': None,
        'access_date': None,
        'doi': None,
        'report_number': None,
        'patent_number': None,
        'degree': None,
        'original': original_ref_text
    }
    
    # 1. 提取編號 [1]
    number_match = re.match(r'^\s*[\[【]\s*(\d+)\s*[\]】]\s*', ref_text)
    if not number_match: return result 
    
    result['ref_number'] = number_match.group(1)
    rest_text = ref_text[number_match.end():].strip()
    
    # === 分流判斷：如果是中文文獻，走新邏輯；如果是英文，走舊邏輯 ===
    if has_chinese(rest_text):
        # ==========================================
        #       中文解析邏輯 (靈活分割)
        # ==========================================
        
        # A. 提取年份
        year_match = re.search(r'\b(19\d{2}|20\d{2})\b', rest_text)
        if year_match: result['year'] = year_match.group(1)
        
        # B. 提取 URL (含 Markdown 格式支援)
        md_link_match = re.search(r'\[([^\]]+)\]\((https?://[^\)]+)\)', rest_text)
        if md_link_match:
            result['url'] = md_link_match.group(2)
            rest_text = rest_text.replace(md_link_match.group(0), "") # 移除連結避免干擾
        else:
            url_match = re.search(r'(https?://[^\s,，。]+)', rest_text)
            if url_match: result['url'] = url_match.group(1).rstrip('.')
            
            doi_match = re.search(r'doi:?\s*(10\.\d{4,}/[^\s,，。]+)', rest_text, re.IGNORECASE)
            if doi_match: result['doi'] = doi_match.group(1).rstrip('.')

        # C. 學位論文識別
        thesis_match = re.search(r'(碩士|博士|學位論文)', rest_text)
        if thesis_match:
            result['source_type'] = 'Thesis/Dissertation'
            result['degree'] = thesis_match.group(1)

        # D. 作者/標題/來源 分割
        # 優先找引號 (IEEE 標準中文)
        quote_match = re.search(r'["“](.+?)["”]', rest_text)
        if quote_match:
            result['title'] = quote_match.group(1).strip()
            before_quote = rest_text[:quote_match.start()].strip().rstrip(',.，。 ')
            if before_quote:
                result['authors'] = before_quote
                result['parsed_authors'] = parse_ieee_authors(before_quote)
            
            after_quote = rest_text[quote_match.end():].strip().lstrip(',.，。 ')
            # 清理已提取的年份/URL
            if result['year']: after_quote = after_quote.replace(result['year'], '').strip().rstrip(',.，。 ')
            if result['url']: after_quote = after_quote.replace(result['url'], '').strip()
            if after_quote: result['source'] = after_quote
        else:
            # 無引號 (靈活分割：作者, 標題, 來源)
            clean_rest = rest_text
            if result['url']: clean_rest = clean_rest.replace(result['url'], '')
            if result['doi']: clean_rest = clean_rest.replace(result['doi'], '')
            if result['year']: clean_rest = re.sub(r'\b'+result['year']+r'\b', '', clean_rest)
            
            parts = re.split(r'[,，.。]', clean_rest)
            parts = [p.strip() for p in parts if p.strip()]
            
            if len(parts) >= 1:
                # 判斷第一段是作者還是標題 (長度判斷)
                if len(parts[0]) < 20: 
                    result['authors'] = parts[0]
                    result['parsed_authors'] = parse_ieee_authors(parts[0])
                    if len(parts) >= 2: result['title'] = parts[1]
                    if len(parts) >= 3: result['source'] = parts[2]
                else:
                    # 第一段太長，視為標題 (無作者)
                    result['title'] = parts[0]
                    result['authors'] = None
                    if len(parts) >= 2: result['source'] = parts[1]

        # 針對學位論文從來源抓學校
        if result['source_type'] == 'Thesis/Dissertation' and result['source']:
            if "大學" in result['source']: result['publisher'] = result['source']

    else:
        # ==========================================
        #       英文解析邏輯 (保留原始邏輯)
        # ==========================================
        
        quote_patterns = [
            (r'"', r'"'), (r'“', r'”'), (r'“', r'“'),  (r'”', r'”'),(r'\'', r'\'')
        ]
        
        title_found = False
        after_title = rest_text 
        
        for open_q, close_q in quote_patterns:
            pattern = re.escape(open_q) + r'(.+?)' + re.escape(close_q)
            match = re.search(pattern, rest_text)
            if match:
                # 抓到標題
                title = match.group(1).strip().rstrip(',.。;；:：')
                result['title'] = title
                # 抓到作者
                before_title = rest_text[:match.start()].strip().rstrip(',. ')
                before_title = re.sub(r'\s+and\s*$', '', before_title, flags=re.IGNORECASE)
                before_title = re.sub(r',?\s*(?:et\s+al\.?|等)\s*$', '', before_title, flags=re.IGNORECASE)
                
                if before_title:
                    result['authors'] = before_title
                    if 'parse_ieee_authors' in globals():
                        result['parsed_authors'] = parse_ieee_authors(before_title)
                
                after_title = rest_text[match.end():].strip()
                title_found = True
                break
                
        # Fallback: 沒引號
        if not title_found:
            year_split_match = re.search(r'(?:,|^)\s*(\d{4}[a-z]?)(?:\.|,)\s*', rest_text)
            if year_split_match:
                authors_candidate = rest_text[:year_split_match.start()].strip().strip(',. ')
                title_candidate = rest_text[year_split_match.end():].strip()
                result['year'] = year_split_match.group(1)

                url_in_author = re.search(r'(?:,|^|\s)(URL|Available|http)', authors_candidate, re.IGNORECASE)
                if url_in_author:
                    after_title = authors_candidate[url_in_author.start():].strip()
                    real_content = authors_candidate[:url_in_author.start()].strip().strip(',. ')
                    dot_split = re.search(r'\.\s+', real_content)
                    if dot_split:
                        result['authors'] = real_content[:dot_split.start() + 1].strip()
                        result['title'] = real_content[dot_split.end():].strip()
                    else:
                        result['authors'] = real_content
                else:
                    result['authors'] = authors_candidate
                    in_split_match = re.search(r'(?:\.|,|\s)\s*(?:In|in):\s*', title_candidate)
                    if in_split_match:
                        result['title'] = title_candidate[:in_split_match.start()].strip().rstrip('.')
                        after_title = title_candidate[in_split_match.end():].strip()
                    else:
                        dot_split_match = re.search(r'\.\s+', title_candidate)
                        if dot_split_match:
                            result['title'] = title_candidate[:dot_split_match.start()].strip()
                            after_title = title_candidate[dot_split_match.end():].strip()
                        else:
                            result['title'] = title_candidate
                            after_title = title_candidate
            else:
                parts = rest_text.split(',', 1)
                if len(parts) > 1:
                    result['authors'] = parts[0].strip()
                    result['title'] = parts[1].strip()
                    after_title = result['title']

        # 特殊修復: Ethereum foundation 等無作者情況
        if not result.get('authors') and result.get('title'):
            eth_split = re.search(r'(Ethereum foundation)\.\s*(.*)', result['title'], re.IGNORECASE)
            author_split = re.search(r'\.\s+([A-Z])', result['title'])
            if eth_split:
                 result['authors'] = eth_split.group(1).strip()
                 result['title'] = eth_split.group(2).strip()
            elif author_split:
                 result['authors'] = result['title'][:author_split.start()].strip()
                 result['title'] = result['title'][author_split.start() + 1:].strip()

        # === [修正] 全局清理 ===
        after_title = re.sub(r'Authorized licensed use[\s\S]*', '', after_title, flags=re.IGNORECASE)
        after_title = re.sub(r'Downloaded\s+on[\s\S]*', '', after_title, flags=re.IGNORECASE)
        after_title = re.sub(r'IEEE Xplore[\s\S]*', '', after_title, flags=re.IGNORECASE).strip()

        # === [關鍵修復] 提前提取年份 ===
        if not result['year']:
            temp_text = re.sub(r'doi:.*', '', after_title, flags=re.IGNORECASE)
            temp_text = re.sub(r'©\s*\d{4}', '', temp_text)
            year_matches = re.findall(r'(?<!:)(?<!arXiv:)\b(19\d{2}|20\d{2})\b(?!\.\d)', temp_text)
            if year_matches: 
                result['year'] = year_matches[-1]

        # === [修正] 年份開頭清理 ===
        if result['year']:
            year_start_match = re.match(r'^\s*(?:[\.,]\s*)?[\(\[]?\s*(\d{4})\s*[\)\]]?[\.,]?\s*', after_title)
            if year_start_match and year_start_match.group(1) == result['year']:
                after_title = after_title[year_start_match.end():].strip()

        # === 3. 提取來源資訊 (原始邏輯) ===
        full_search_text = after_title 
        
        vol_match = re.search(r'\b(?:Vol\.?|Volume|卷|第\s*\d+\s*卷)\s*(\d+)', full_search_text, re.IGNORECASE)
        if not vol_match: vol_match = re.search(r'第\s*(\d+)\s*卷', full_search_text)
        if vol_match: result['volume'] = vol_match.group(1)
        
        no_match = re.search(r'\b(?:no\.?|期|第\s*\d+\s*期)\s*(\d+)', full_search_text, re.IGNORECASE)
        if not no_match: no_match = re.search(r'第\s*(\d+)\s*期', full_search_text)
        if no_match: result['issue'] = no_match.group(1)
        
        pp_match = re.search(r'\b(?:pp?\.?|Pages?|Page\s*No\.?|頁)\s*(\d+(?:\s*(?:[\–\-—]|to)\s*\d+)?)', full_search_text, re.IGNORECASE)
        if pp_match: 
            raw_pages = pp_match.group(1)
            result['pages'] = re.sub(r'\s+', '', raw_pages).replace('to', '-').replace('–', '-').replace('—', '-')

        if not result['year']:
            clean_year_text = re.sub(r'doi:.*', '', full_search_text, flags=re.IGNORECASE)
            clean_year_text = re.sub(r'©\s*\d{4}', '', clean_year_text)
            year_matches = re.findall(r'(?<!:)(?<!arXiv:)\b(19\d{2}|20\d{2})\b(?!\.\d)', clean_year_text)
            if year_matches: result['year'] = year_matches[-1]

        months_regex = r'\b(?:Jan\.|Jan|January|Feb\.|Feb|February|Mar\.|Mar|March|Apr\.|Apr|April|May\.?|May|Jun\.|Jun|June|Jul\.|Jul|July|Aug\.|Aug|August|Sep\.|Sep|Sept\.|September|Oct\.|Oct|October|Nov\.|Nov|November|Dec\.|Dec|December)\b'
        end_indicators = [
            r'\b(?:Vol\.?|Volume|卷|第\s*\d+\s*卷)\s*\d+', 
            r'\b(?:no\.?|期|第\s*\d+\s*期)\s*\d+', 
            r'\b(?:pp?\.?|Pages?|Page|頁)\s*\d+', 
            r'(?<!:)\b19\d{2}\b', 
            r'(?<!:)\b20\d{2}\b', 
            r'doi:', 
            months_regex
        ]
        min_pos = len(full_search_text)
        
        for ind in end_indicators:
            matches = list(re.finditer(ind, full_search_text, re.IGNORECASE))
            for m in matches:
                if (r'19\d{2}' in ind or r'20\d{2}' in ind):
                    context_after = full_search_text[m.end():]
                    if re.search(r'(卷|期|頁)', full_search_text[m.end():m.end()+5]): 
                        if m.start() < min_pos: min_pos = m.start()
                        continue
                    if m.start() < 5 and re.search(r'[a-zA-Z]', context_after): continue 
                    if re.search(r'\b(Conference|Symposium|Workshop|Congress|Meeting|Lecture Notes|Proceedings)\b', full_search_text[m.end():m.end()+60], re.IGNORECASE):
                        continue
                if m.start() < min_pos:
                    min_pos = m.start()
                    break
        
        source_candidate = full_search_text[:min_pos].strip().strip(',. -')
        
        clean_source = re.sub(r'^in(?:[:\s]+|$)', '', source_candidate, flags=re.IGNORECASE)
        clean_source = re.sub(r'^(?:收錄於|載於|刊於)[:\s]*', '', clean_source)
        clean_source = re.sub(r'\[[JCD]\]', '', clean_source)
        clean_source = re.sub(r'^J\.\s+', '', clean_source)
        clean_source = re.sub(r'(?:Retrieved from|Available:|http).*', '', clean_source, flags=re.IGNORECASE)
        clean_source = re.sub(r'\[Online\]\.?', '', clean_source, flags=re.IGNORECASE).strip().strip(',. -')
        
        result['source'] = clean_source

        # Source Type
        if re.search(r'(Proc\.|Proceedings|Conference|Symposium|Workshop)', full_search_text, re.IGNORECASE):
            result['source_type'] = 'Conference Paper'
            result['conference_name'] = clean_source
        elif re.search(r'(vol\.|volume|no\.|number)', full_search_text, re.IGNORECASE) and not result['conference_name']:
            result['source_type'] = 'Journal Article'
            result['journal_name'] = clean_source
        elif re.search(r'(Ph\.D\.|M\.S\.|thesis)', full_search_text, re.IGNORECASE):
            result['source_type'] = 'Thesis/Dissertation'
        elif re.search(r'(Tech\. Rep\.|Technical Report)', full_search_text, re.IGNORECASE):
            result['source_type'] = 'Technical Report'
            rep_match = re.search(r'(Tech\.\s+Rep\.|Rep\.)\s+([\w\-]+)', full_search_text, re.IGNORECASE)
            if rep_match: result['report_number'] = rep_match.group(2)
        elif re.search(r'Patent', full_search_text, re.IGNORECASE):
            result['source_type'] = 'Patent'
        elif re.search(r'\[Online\]|Available:|https?://|arxiv\.org', full_search_text, re.IGNORECASE):
            result['source_type'] = 'Website/Online'
        elif re.search(r'(Ed\.|Eds\.|edition)', full_search_text, re.IGNORECASE):
            result['source_type'] = 'Book'

        # Month
        months_list = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Sept", "Oct", "Nov", "Dec", "January", "February", "March", "April", "June", "July", "August", "September", "October", "November", "December"]
        month_part = r'(?:' + '|'.join(months_list) + r')\.?'
        comp_month_match = re.search(r'\b' + month_part + r'\s*[-/–]\s*' + month_part + r'\b', full_search_text, re.IGNORECASE)
        if comp_month_match:
            result['month'] = comp_month_match.group(0)
        else:
            month_match = re.search(months_regex, full_search_text, re.IGNORECASE)
            if month_match: result['month'] = month_match.group(0)
        
        # DOI
        doi_match = re.search(r'(?:doi:|DOI:|https?://doi\.org/)\s*(10\.\d{4,}/[^\s,;\]\)]+)', full_search_text)
        if doi_match: result['doi'] = doi_match.group(1).rstrip('.')
        
        # URL
        pdf_url_match = re.search(r'(?:Available:|Retrieved from|URL)\s*(https?://.*?\.pdf)', full_search_text, re.IGNORECASE)
        if pdf_url_match:
            result['url'] = pdf_url_match.group(1).replace(' ', '').strip()
        else:
            url_match = re.search(r'(?:Available:|Retrieved from|URL)\s*(https?://[^,\n\s\]\)]+)', full_search_text, re.IGNORECASE)
            if url_match:
                result['url'] = url_match.group(1).strip()
            elif not result['url']:
                gen_url = re.search(r'(https?://[^\s,;]+(?:\.pdf)?)', full_search_text, re.IGNORECASE)
                if gen_url: result['url'] = gen_url.group(1).strip()

        if result['url'] and 'doi.org' in result['url'] and result['doi']: result['url'] = None
        if result['source'] and re.fullmatch(r'(URL|Available|Online|Retrieved|Website)', result['source'], re.IGNORECASE): result['source'] = None
        
        # Access Date
        acc_match = re.search(r'(?:accessed|retrieved|downloaded)\s+(?:on\s+)?([A-Za-z]+\.?\s+\d{1,2},?\s*\d{4})', full_search_text, re.IGNORECASE)
        if acc_match: result['access_date'] = acc_match.group(1)

    return result


# ===== IEEE 斷行合併 =====
def merge_references_ieee_strict(paragraphs):
    """
    [NEW from test1204-6] [IEEE 專用模式] 嚴格合併
    只認 [n] 開頭，其他一律視為上一行的延續。
    解決 Mar. 2022 或 斷行 DOI 問題。
    """
    merged = []
    current_ref = ""
    pattern_index = re.compile(r'^\s*[\[【]\s*\d+\s*[】\]]')
    
    for para in paragraphs:
        para = para.strip()
        if not para: continue
        
        # 排除純數字頁碼
        if para.isdigit() and len(para) < 5: continue
        
        if pattern_index.match(para):
            if current_ref:
                merged.append(current_ref)
            current_ref = para
        else:
            if current_ref:
                # 處理斷字
                if current_ref.endswith('-'):
                    # URL 斷行保護：如果下一行是小寫/數字開頭，保留連字號
                    if para and (para[0].islower() or para[0].isdigit()):
                        current_ref = current_ref + para  # 保留連字號
                    else:
                        current_ref = current_ref[:-1] + para  # 一般斷字，移除連字號
                # 處理中英文間距
                elif has_chinese(current_ref[-1:]) and has_chinese(para[:1]):
                    current_ref += para
                else:
                    current_ref += " " + para
            else:
                current_ref = para
                
    if current_ref: merged.append(current_ref)
    return merged


# ===== IEEE 格式轉換 =====
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