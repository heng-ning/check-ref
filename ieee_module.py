# ===== IEEE 作者解析 =====
def parse_ieee_authors(authors_str):
    """
    [Fixed] 解析 IEEE 作者字串，強力修復 'and' 殘留問題
    Input: "D. Yang, J. Gavigan, and Z. Wilcox-O’Hearn"
    Output: [{'first': 'D.', 'last': 'Yang'}, {'first': 'Z.', 'last': "Wilcox-O’Hearn"}]
    """
    
    if not authors_str:
        return []

    # 1. 預處理：將 " and " 替換為逗號，避免混淆名字解析
    # 使用 re.IGNORECASE 確保 'And' 或 'AND' 都能被抓到
    clean_str = re.sub(r',?\s+\b(and|&)\b\s+', ',', authors_str, flags=re.IGNORECASE)
    
    # 2. 根據逗號分割作者
    # 移除多餘空白
    raw_authors = [a.strip() for a in clean_str.split(',') if a.strip()]
    
    parsed_list = []
    
    for auth in raw_authors:
        # 處理 "Last, First" 格式 (有些 IEEE 變體)
        if ',' in auth:
            parts = auth.split(',', 1)
            parsed_list.append({
                'last': parts[0].strip(),
                'first': parts[1].strip()
            })
            continue
            
        # 處理標準 "First M. Last" 格式
        # 以空格分割
        parts = auth.split()
        if not parts:
            continue
            
        if len(parts) == 1:
            # 只有一個字，假定為 Last Name
            parsed_list.append({'first': '', 'last': parts[0]})
        else:
            # 最後一個部分當作 Last Name
            # 前面所有部分當作 First Name (包含 Middle Name)
            last_name = parts[-1]
            first_name = " ".join(parts[:-1])
            
            # [特例處理]：如果名字裡還有殘留的 'and' (極端情況)，再清一次
            first_name = re.sub(r'\band\b', '', first_name, flags=re.IGNORECASE).strip()
            
            parsed_list.append({
                'first': first_name,
                'last': last_name
            })
            
    return parsed_list

# ===== IEEE 完整解析 =====
def extract_ieee_reference_full(ref_text):
    """
    [Final Fixed Version] 完整解析 IEEE 格式參考文獻
    包含針對 Ethereum, arXiv, BitTicket, DOI重複, 頁碼to, 年份誤刪, 月份誤判, Downloaded清理 等所有案例的修復。
    """
    
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
        'original': ref_text
    }
    
    # 1. 提取編號 [1]
    number_match = re.match(r'^\s*[\[【]\s*(\d+)\s*[\]】]\s*', ref_text)
    if not number_match: return result 
    
    result['ref_number'] = number_match.group(1)
    rest_text = ref_text[number_match.end():].strip()
    
    # === 2. 提取作者和標題 ===
    quote_patterns = [
        (r'"', r'"'), (r'“', r'”'), (r'“', r'“'),  (r'”', r'”'),(r'\'', r'\''), (r'「', r'」')
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
            before_title = re.sub(r',?\s*et\s+al\.?$', '', before_title, flags=re.IGNORECASE)
            if before_title:
                result['authors'] = before_title
                if 'parse_ieee_authors' in globals():
                    result['parsed_authors'] = parse_ieee_authors(before_title)
            
            after_title = rest_text[match.end():].strip()
            title_found = True
            break
            
    # Fallback: 沒引號，啟動智慧救援
    if not title_found:
        year_split_match = re.search(r'(?:,|^)\s*(\d{4}[a-z]?)(?:\.|,)\s*', rest_text)
        if year_split_match:
            authors_candidate = rest_text[:year_split_match.start()].strip().strip(',. ')
            title_candidate = rest_text[year_split_match.end():].strip()
            result['year'] = year_split_match.group(1)

            # 檢查作者欄位是否誤含 URL
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

    # === [修正] 全局清理：移除資料庫授權聲明與下載資訊 ===
    after_title = re.sub(r'Authorized licensed use[\s\S]*', '', after_title, flags=re.IGNORECASE)
    after_title = re.sub(r'Downloaded\s+on[\s\S]*', '', after_title, flags=re.IGNORECASE)
    after_title = re.sub(r'IEEE Xplore[\s\S]*', '', after_title, flags=re.IGNORECASE).strip()

    # === [關鍵修復] 如果 Source 開頭是年份，且後面接標點 (如 "2019, - 4th"), 移除 ===
    # 若後面只有空格 (如 "2019 34th"), 則保留
    if not result['year']:
        # 先暫時清理干擾項以抓取準確年份
        temp_text = re.sub(r'doi:.*', '', after_title, flags=re.IGNORECASE)
        temp_text = re.sub(r'©\s*\d{4}', '', temp_text)
        # 排除 arXiv 編號中的年份 (如 2001.xxxxx)
        year_matches = re.findall(r'(?<!:)(?<!arXiv:)\b(19\d{2}|20\d{2})\b(?!\.\d)', temp_text)
        if year_matches: 
            result['year'] = year_matches[-1]
    if result['year']:
        # [修正] 加入點號 \. 到允許的分隔符列表中
        year_start_match = re.match(r'^\s*(?:[\.,]\s*)?[\(]?\s*(\d{4})\s*[\)]?[\.,]?\s*', after_title)
        if year_start_match and year_start_match.group(1) == result['year']:
            after_title = after_title[year_start_match.end():].strip()

    # === 3. 提取來源資訊 ===
    full_search_text = after_title # 經過清理後的乾淨文本
    
    # Vol
    vol_match = re.search(r'\b(?:Vol\.?|Volume)\s*(\d+)', full_search_text, re.IGNORECASE)
    if vol_match: result['volume'] = vol_match.group(1)
    
    # No (排除 Page No.)
    no_match = re.search(r'\b(?<!Page\s)no\.?\s*(\d+)', full_search_text, re.IGNORECASE)
    if no_match: result['issue'] = no_match.group(1)
    
    # Pages (支援 pp, Page No., Page)
    pp_match = re.search(r'\b(?:pp?\.?|Pages?|Page\s*No\.?)\s*(\d+(?:\s*(?:[\–\-—]|to)\s*\d+)?)', full_search_text, re.IGNORECASE)
    if pp_match: 
        raw_pages = pp_match.group(1)
        result['pages'] = re.sub(r'\s+', '', raw_pages).replace('to', '-').replace('–', '-').replace('—', '-')

    # 年份 (補抓)
    if not result['year']:
        clean_year_text = re.sub(r'doi:.*', '', full_search_text, flags=re.IGNORECASE)
        clean_year_text = re.sub(r'©\s*\d{4}', '', clean_year_text)
        year_matches = re.findall(r'(?<!:)(?<!arXiv:)\b(19\d{2}|20\d{2})\b(?!\.\d)', clean_year_text)
        if year_matches: result['year'] = year_matches[-1]

    # Source Name 截斷
    months_regex = r'\b(?:Jan\.|Jan|January|Feb\.|Feb|February|Mar\.|Mar|March|Apr\.|Apr|April|May\.?|May|Jun\.|Jun|June|Jul\.|Jul|July|Aug\.|Aug|August|Sep\.|Sep|Sept\.|September|Oct\.|Oct|October|Nov\.|Nov|November|Dec\.|Dec|December)\b'
    end_indicators = [
        r'\b(?:Vol\.?|Volume)\s*\d+',      
        r'\bno\.?\s*\d+', 
        r'\b(?:pp?\.?|Pages?|Page)\s*\d+', # [修正] 強制 Page 後面要有數字，避免誤切
        r'(?<!:)\b19\d{2}\b', 
        r'(?<!:)\b20\d{2}\b', 
        r'doi:', 
        months_regex
    ]
    min_pos = len(full_search_text)
    
    for ind in end_indicators:
        matches = list(re.finditer(ind, full_search_text, re.IGNORECASE))
        for m in matches:
            # 保護機制: 略過開頭的年份或會議關鍵字後面的年份
            if (r'19\d{2}' in ind or r'20\d{2}' in ind):
                context_after = full_search_text[m.end():]
                if m.start() < 5 and re.search(r'[a-zA-Z]', context_after): continue 
            # [修正] 加入 Lecture Notes, Proceedings 等保護關鍵字
                if re.search(r'\b(Conference|Symposium|Workshop|Congress|Meeting|Lecture Notes|Proceedings)\b',     full_search_text[m.end():m.end()+60], re.IGNORECASE):
                    continue
            if m.start() < min_pos:
                min_pos = m.start()
                break
    
    source_candidate = full_search_text[:min_pos].strip().strip(',. -')
    # 清理 Source
    clean_source = re.sub(r'^in(?:[:\s]+|$)', '', source_candidate, flags=re.IGNORECASE)
    clean_source = re.sub(r'^J\.\s+', '', clean_source)
    clean_source = re.sub(r'(?:Retrieved from|Available:|http).*', '', clean_source, flags=re.IGNORECASE)
    # [新增] 移除 [Online] 標記
    clean_source = re.sub(r'\[Online\]\.?', '', clean_source, flags=re.IGNORECASE).strip().strip(',. -')
    
    result['source'] = clean_source

    # === 4. Source Type & Details ===
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

    # === [關鍵修復] 月份提取 (優先匹配複合月份) ===
    months_list = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Sept", "Oct", "Nov", "Dec", 
                   "January", "February", "March", "April", "June", "July", "August", "September", "October", "November", "December"]
    month_part = r'(?:' + '|'.join(months_list) + r')\.?'
    # 複合月份 (Month-Month)
    comp_month_match = re.search(r'\b' + month_part + r'\s*[-/–]\s*' + month_part + r'\b', full_search_text, re.IGNORECASE)
    if comp_month_match:
        result['month'] = comp_month_match.group(0)
    else:
        month_match = re.search(months_regex, full_search_text, re.IGNORECASE)
        if month_match: result['month'] = month_match.group(0)
    
    # DOI
    doi_match = re.search(r'(?:doi:|DOI:|https?://doi\.org/)\s*(10\.\d{4,}/[^\s,;\]\)]+)', full_search_text)
    if doi_match: result['doi'] = doi_match.group(1).rstrip('.')
    
    # === [關鍵修復] URL 提取 (支援空格合併) ===
    # 策略 1: 針對 .pdf 結尾的連結，允許中間有空格
    pdf_url_match = re.search(r'(?:Available:|Retrieved from|URL)\s*(https?://.*?\.pdf)', full_search_text, re.IGNORECASE)
    if pdf_url_match:
        result['url'] = pdf_url_match.group(1).replace(' ', '').strip()
    else:
        # 策略 2: 標準提取
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
                # 萬一第一行就沒抓到編號，先當作第一條
                current_ref = para
                
    if current_ref: merged.append(current_ref)
    return merged

# ===== IEEE 格式轉換 =====
def convert_en_ieee_to_apa(data):
    """
    將解析後的 IEEE 資料轉換為標準 APA 7 格式
    修復重點：
    1. 作者連接詞 (&) 邏輯改用列表處理，避免正則誤判。
    2. 增加卷號 (Volume) 斜體、期號 (Issue) 正體、頁碼的標準格式處理。
    3. 確保每個區塊結尾都有正確的句號。
    """
    
    # === 1. 作者 (Authors) ===
    # 格式: Last, F. M., & Last, F. M.
    apa_authors = []
    parsed = data.get('parsed_authors', [])
    
    # 如果有解析好的作者資料
    if parsed:
        for auth in parsed:
            last = auth.get('last', '').strip()
            first = auth.get('first', '').strip()
            # 簡單檢查：如果 first 沒有句點且長度為 1 (如 "P")，補上句點
            if len(first) == 1 and first.isalpha():
                first += "."
            apa_authors.append(f"{last}, {first}")
    elif data.get('authors'):
        # Fallback: 如果沒解析成功，直接用原始字串
        apa_authors.append(data['authors'])

    # 組合作者字串
    if not apa_authors:
        auth_str = ""
    elif len(apa_authors) == 1:
        auth_str = apa_authors[0]
    elif len(apa_authors) == 2:
        # 兩位作者用 & 連接 (無逗號)
        auth_str = f"{apa_authors[0]} & {apa_authors[1]}"
    else:
        # 三位以上，最後一位前加 comma 和 &
        auth_str = ", ".join(apa_authors[:-1]) + f", & {apa_authors[-1]}"
    
    if auth_str and not auth_str.endswith('.'):
        auth_str += "."

    # === 2. 年份 (Year) ===
    # 格式: (2020).
    year_str = ""
    if data.get('year'):
        # 清理可能存在的括號，確保只有數字
        clean_year = str(data['year']).replace('(', '').replace(')', '').strip()
        year_str = f"({clean_year})."

    # === 3. 標題 (Title) ===
    # 格式: Title of the article.
    title_str = data.get('title', '').strip()
    if title_str:
        # 移除標題末尾原本的標點，統一加句號
        title_str = title_str.rstrip(',.;') 
        title_str += "."

    # === 4. 來源 (Source details) ===
    # 格式: *Journal Name*, *Volume*(Issue), Pages.
    # 注意: Markdown *text* 用於斜體
    source_parts = []
    
    # 來源名稱 (期刊/書名) -> 斜體
    if data.get('source'):
        source_parts.append(f"*{data['source']}*")
    
    # 卷號 (斜體) 與 期號 (括號，正體)
    if data.get('volume'):
        vol_info = f"*{data['volume']}*" # 卷號斜體
        if data.get('issue'):
            vol_info += f"({data['issue']})" # 期號緊接卷號，無空格
        source_parts.append(vol_info)
    elif data.get('issue'):
        # 只有期號的情況
        source_parts.append(f"({data['issue']})")
         
    # 頁碼
    if data.get('pages'):
        source_parts.append(data['pages'])

    # 組合來源字串
    source_str = ", ".join(source_parts)
    if source_str and not source_str.endswith('.'):
        source_str += "."

    # === 5. DOI / URL ===
    # 格式: https://doi.org/10.xxxx
    doi_str = ""
    if data.get('doi'):
        clean_doi = data['doi'].replace('doi:', '').strip()
        # 移除已經存在的 https://doi.org/ 前綴避免重複
        clean_doi = clean_doi.replace('https://doi.org/', '').replace('http://dx.doi.org/', '')
        doi_str = f"https://doi.org/{clean_doi}"
    elif data.get('url'):
        doi_str = data['url']

    # === 最終組合 ===
    # 過濾掉空字串並用空格連接
    parts = [p for p in [auth_str, year_str, title_str, source_str, doi_str] if p]
    return " ".join(parts)

# 引入：
import re
from common_utils import (
    has_chinese,
)