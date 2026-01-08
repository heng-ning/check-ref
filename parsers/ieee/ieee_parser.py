import re
from utils.text_processor import (
    normalize_text,
    normalize_chinese_text,
    has_chinese
)
from parsers.apa.apa_parser_en import extract_apa_en_detailed
from parsers.apa.apa_parser_zh import extract_apa_zh_detailed
from parsers.apa.apa_merger import find_apa_head

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

def extract_ieee_reference_full(ref_text: str) -> dict:
    ref_text = normalize_text(ref_text)

    # 先解析前面的 [n]，並拿到 rest_text
    m = re.match(r'^\s*[\[【]\s*(\d+)\s*[】\]]\s*(.*)$', ref_text)
    if m:
        ref_number = m.group(1)
        rest_text = m.group(2).strip()
    else:
        ref_number = None
        rest_text = ref_text

    # ★ 唯一的「編號 + APA」判斷：用去編號後的 rest_text
    looks_like_ieee = bool(re.search(r'\bRFC\s+\d+|\[Online\]|Available:|Retrieved from|https?://|[“”"]', rest_text, re.IGNORECASE))
    if find_apa_head(rest_text) and not looks_like_ieee:
    #if find_apa_head(rest_text):
        
        if has_chinese(rest_text):
            data = extract_apa_zh_detailed(rest_text)
        else:
            data = extract_apa_en_detailed(rest_text)
        data["ref_number"] = ref_number
        data["format"] = "IEEE-APA"
        return data

    # 下面才開始 IEEE 專用 result 初始化與解析
    original_ref_text = ref_text
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
        'editors': None, 
        'url': None,
        'access_date': None,
        'doi': None,
        'report_number': None,
        'patent_number': None,
        'degree': None,
        'original': original_ref_text
    }

    # 1. 提取編號 [1]
    number_match = re.match(r'^\s*(?:[\[【\(]?\s*(\d+)\s*[\]】\)\.]?)\.?\s+', ref_text)
    
    if not number_match: return result 
    
    result['ref_number'] = number_match.group(1)
    rest_text = ref_text[number_match.end():].strip()
    
    # === 分流判斷：如果是中文文獻，走新邏輯；如果是英文，走舊邏輯 ===
    if has_chinese(rest_text):
        # ==========================================
        #       中文解析邏輯
        # ==========================================
        
        # A. 提取年份
        year_match = re.search(r'\b(19\d{2}|20\d{2})\b', rest_text)
        if year_match: result['year'] = year_match.group(1)
        
        # B. 提取 URL (含 Markdown 格式支援)
        md_link_match = re.search(r'\[([^\]]+)\]\((https?://[^\)]+)\)', rest_text)
        if md_link_match:
            raw_url = md_link_match.group(2)
            # [修正] 移除 URL 末尾的點或逗號，但保留路徑中的斜線
            result['url'] = raw_url.rstrip('.,;，。')
            rest_text = rest_text.replace(md_link_match.group(0), "") 
        else:
            url_match = re.search(r'(https?://[^\s]+)', rest_text)
            if url_match: 
                # 移除 URL 末尾常見的標點符號，但小心不要移除路徑中的斜線
                raw_url = url_match.group(1)
                result['url'] = raw_url.rstrip('.,;，。)]}').strip()
            
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
            result['title'] = quote_match.group(1).strip().rstrip('.,;，。、')
            before_quote = rest_text[:quote_match.start()].strip().rstrip(',.，。 ')
            if before_quote:
                result['authors'] = before_quote
                result['parsed_authors'] = parse_ieee_authors(before_quote)
            
            after_quote = rest_text[quote_match.end():].strip().lstrip(',.，。 ')
            # 清理已提取的年份/URL
            if result['year']: after_quote = after_quote.replace(result['year'], '').strip().rstrip(',.，。 ')
            if result['url']: after_quote = after_quote.replace(result['url'], '').strip()
            
            cleaned_source = clean_source_text(after_quote)
            if cleaned_source: result['source'] = cleaned_source
        else:
            # 無引號 (靈活分割：作者, 標題, 來源)
            clean_rest = rest_text
            if result['url']: clean_rest = clean_rest.replace(result['url'], '')
            if result['doi']: clean_rest = clean_rest.replace(result['doi'], '')
            if result['year']: clean_rest = re.sub(r'\b'+result['year']+r'\b', '', clean_rest)

            clean_rest = re.sub(r'\(?\s*accessed\.?.*', '', clean_rest, flags=re.IGNORECASE)

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
        #       英文解析邏輯
        # ==========================================

        # === 標準 (Standard) 文獻專用解析 ===
        # 格式範例：[2] IEEE Transformer Committee, ANSI standard C57.13-1993, March 1994, IEEE Standard Requirements...
        std_match = re.search(r'\b(IEEE|ANSI|ISO|IEC)\s+(?:Std|Standard)\.?\s+([\w\d\.\-]+)', rest_text, re.IGNORECASE)
        
        is_standard_ref = False
        if std_match:
            # 如果沒有引號包住標題，且有逗號分隔，判定為標準格式
            if not re.search(r'["“].+["”]', rest_text) and ',' in rest_text:
                is_standard_ref = True

        title_found = False
        after_title = rest_text 

        if is_standard_ref:
            result['source_type'] = 'Standard'
            parts = [p.strip() for p in rest_text.split(',') if p.strip()]
            
            if len(parts) > 0:
                result['authors'] = parts[0] # 第一段：IEEE Transformer Committee
            
            # 尋找年份與標題切分點
            year_index = -1
            for i, part in enumerate(parts):
                # 排除第一段 (作者)
                if i == 0: continue
                
                # 找獨立年份 (1994) 或 月份+年份 (March 1994)
                # 注意排除標準編號中的年份 (C57.13-1993)
                y_match = re.search(r'\b(19\d{2}|20\d{2})\b', part)
                if y_match:
                    # 檢查是否緊跟在連字號後 (編號特徵)
                    if re.search(r'-\d{4}', part):
                        continue 
                    
                    result['year'] = y_match.group(1)
                    year_index = i
                    
                    # 提取月份
                    if re.search(r'[a-zA-Z]', part): # 如果包含字母，可能是 "March 1994"
                        result['month'] = part.replace(result['year'], '').strip()
                    break
            
            # 分配 Source (標準編號) 和 Title
            if year_index != -1:
                # 年份中間：作者 , [Source] , [Year] , [Title]
                # 來源 = 作者與年份中間的部分
                if year_index > 1:
                    result['source'] = ", ".join(parts[1:year_index])
                
                # 標題 = 年份之後的部分
                if year_index < len(parts) - 1:
                    result['title'] = ", ".join(parts[year_index+1:])
            else:
                # 沒找到年份：假設最後一段是標題，中間是來源
                if len(parts) >= 2:
                    result['title'] = parts[-1]
                    result['source'] = ", ".join(parts[1:-1])

            title_found = True
            after_title = ""

        else:
            quote_patterns = [
                (r'"', r'"'), (r'“', r'”'), (r'“', r'“'),  (r'”', r'”'),(r'\'', r'\'')
            ]
            
            for open_q, close_q in quote_patterns:
                pattern = re.escape(open_q) + r'(.+?)' + re.escape(close_q)
                match = re.search(pattern, rest_text)
                if match:
                    title = match.group(1).strip().rstrip(',.。;；:：')
                    result['title'] = title
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
                
        # 沒引號
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

        # Ethereum foundation 等無作者情況
        if not result.get('authors') and result.get('title'):
            eth_split = re.search(r'(Ethereum foundation)\.\s*(.*)', result['title'], re.IGNORECASE)
            author_split = re.search(r'\.\s+([A-Z])', result['title'])
            if eth_split:
                result['authors'] = eth_split.group(1).strip()
                result['title'] = eth_split.group(2).strip()
            elif author_split:
                result['authors'] = result['title'][:author_split.start()].strip()
                result['title'] = result['title'][author_split.start() + 1:].strip()

        # === 提取編輯者 (Editors) ===
        # 尋找類似 "In: Name1, Name2 (eds)" 的結構, 支援 (eds), (ed.), (eds.), (Ed.), (Eds.)
        editor_match = re.search(r'\bIn\s*:\s*(.+?)\s*\(?([Ee]ds?\.?)\)?', after_title)
        
        if editor_match:
            # 群組 1 是編輯者姓名字串 (e.g., "Pérez-Solà C., Navarro-Arribas G.")
            raw_editors = editor_match.group(1).strip()
            result['editors'] = raw_editors

            # 將編輯者資訊從 after_title 中移除，避免干擾後續 Source 解析
            # 移除整段 "In: ... (eds)"
            start, end = editor_match.span()
            
            # 將這段挖掉，用一個空格取代
            after_title = after_title[:start] + " " + after_title[end:]
            after_title = after_title.strip()
            
            # 有時候 (eds) 後面會緊接書名或會議名，移除後可能會有殘留的標點
            after_title = after_title.lstrip(',. :')

        # 1. 嘗試抓取 Markdown 連結 [text](url)
        # 放寬條件：允許 ] 與 ( 中間有空白
        md_link_match = re.search(r'\[([^\]]+)\]\s*\((https?://[^\)]+)\)', after_title)
        
        if md_link_match:
            base_url = md_link_match.group(2).strip()
            md_start_pos = md_link_match.start() # 記錄 Markdown 開始位置
            md_end_pos = md_link_match.end()     # 記錄 Markdown 結束位置
            
            # 從 Markdown 結束的地方往後看
            rest_part = after_title[md_end_pos:]
            
            # 使用 Regex 抓取後續的「碎片」
            # Regex: 抓取直到遇到逗號或年份 (加入 re.DOTALL 處理換行)
            fragment_match = re.match(r'^(.*?)(?=[,;]|\s+(?:19|20)\d{2}\b)', rest_part, re.DOTALL)
            
            full_url = base_url
            total_cut_length = 0 # 額外要切掉的長度
            
            if fragment_match:
                fragment = fragment_match.group(1)
                # 只有當碎片包含斜線(/) 或點號(.) 時才認為它是 URL 的一部分
                if '/' in fragment or '.pdf' in fragment.lower():
                    # 拼接 URL (去除空白)
                    full_url += fragment.replace(' ', '').replace('\n', '')
                    total_cut_length = len(fragment)
            
            result['url'] = full_url
            
            # 新的 after_title = Markdown 前面的部分 + (Markdown結束點 + 碎片長度) 後面的部分
            cut_point = md_end_pos + total_cut_length
            
            # 切除中間那段 URL 相關的文字
            after_title = after_title[:md_start_pos] + " " + after_title[cut_point:]
            
            # 移除可能殘留的標點
            after_title = after_title.replace(' , ', ', ').strip()

        # 2. 如果沒有 Markdown，嘗試直接抓取 .pdf 結尾的 URL (Backup Strategy)
        elif re.search(r'\.pdf', after_title, re.IGNORECASE):
            pdf_wide_match = re.search(r'(https?://[\s\S]*?\.pdf)', after_title, re.IGNORECASE)
            if pdf_wide_match:
                raw_url = pdf_wide_match.group(1)
                result['url'] = raw_url.replace(' ', '').replace('\n', '')
            
                # 同樣使用位置截斷
                start, end = pdf_wide_match.span()
                after_title = after_title[:start] + " " + after_title[end:]
                after_title = after_title.strip()

        non_journal_keywords = [
        "Online document", "Online", "Available", "Retrieved from", 
        "Accessed on", "Internet", "Web page", "White paper"
        ]
    
        # 檢查 after_title 開頭是否包含這些雜訊
        for keyword in non_journal_keywords:
            pattern = r'^[\W_]*' + re.escape(keyword) + r'[\W_]*'
            if re.match(pattern, after_title, re.IGNORECASE):
                after_title = re.sub(pattern, '', after_title, flags=re.IGNORECASE).strip()
        
        # === 全局清理 ===
        after_title = re.sub(r'Authorized licensed use[\s\S]*', '', after_title, flags=re.IGNORECASE)
        after_title = re.sub(r'Downloaded\s+on[\s\S]*', '', after_title, flags=re.IGNORECASE)
        after_title = re.sub(r'IEEE Xplore[\s\S]*', '', after_title, flags=re.IGNORECASE).strip()

        # === 提前提取年份 ===
        if not result['year']:
            temp_text = re.sub(r'doi:.*', '', after_title, flags=re.IGNORECASE)
            temp_text = re.sub(r'©\s*\d{4}', '', temp_text)
            
            # [New] 先把頁碼範圍 (如 2023-2027) 模糊化，避免誤判為年份
            # 尋找 "數字-數字" 格式，且數字看起來像年份的
            temp_text = re.sub(r'\b(19|20)\d{2}\s*[-–]\s*(19|20)\d{2}\b', 'PAGE_RANGE', temp_text)
            # 也要處理 "pp. 2023-2027" 這種格式
            temp_text = re.sub(r'(?:pp\.?|Pages?|頁)\s*\d+(?:[-–]\d+)?', 'PAGE_INFO', temp_text, flags=re.IGNORECASE)

            year_matches = re.findall(r'(?<!:)(?<!arXiv:)\b(19\d{2}|20\d{2})\b(?!\.\d)', temp_text)
            if year_matches: 
                result['year'] = year_matches[-1]

        # === 年份開頭清理 ===
        if result['year']:
            year_start_match = re.match(r'^\s*(?:[\.,]\s*)?[\(\[]?\s*(\d{4})\s*[\)\]]?[\.,]?\s*', after_title)
            
            if year_start_match and year_start_match.group(1) == result['year']:
                # 取得切除年份後剩下的字串
                potential_rest = after_title[year_start_match.end():].strip()
                
                # 保護機制：如果剩下的字串是以 "25th", "1st" 或 "Conference" 開頭
                # 代表這個年份其實是會議名稱的一部分 (如 "2018 25th APSEC")，不該被切除
                is_part_of_title = False
                
                # 檢查 1: 序數詞 (25th, 1st...)
                if re.match(r'^(?:\d+)?(st|nd|rd|th)\b', potential_rest, re.IGNORECASE):
                    is_part_of_title = True
                    
                # 檢查 2: 會議關鍵字 (Conference, IEEE...)
                # 有時候年份後面直接接會議名，如 "2018 IEEE International..."
                if re.match(r'^(IEEE|ACM|International|Conference|Symposium|Workshop)', potential_rest, re.IGNORECASE):
                    is_part_of_title = True

                # 只有在「不是」會議標題的一部分時，才真正執行切除
                if not is_part_of_title:
                    after_title = potential_rest

        # === 3. 提取來源資訊 (原始邏輯) ===
        full_search_text = after_title
        pub_year_match = re.search(r'\b(IEEE|ACM|Springer|Wiley|Elsevier)\s*,\s*(\d{4})', full_search_text, re.IGNORECASE)
        if pub_year_match:
            publisher_candidate = pub_year_match.group(1)
            year_candidate = pub_year_match.group(2)
            
            # 如果抓到的年份跟主要年份一樣 (或主要年份還沒抓到)
            if not result['year'] or year_candidate == result['year']:
                result['publisher'] = publisher_candidate
                if not result['year']: result['year'] = year_candidate
                
                # 將這段 (IEEE, 2017) 從 full_search_text 中移除，避免干擾後續 Source 解析
                # 使用 replace 並處理可能殘留的標點
                full_search_text = full_search_text.replace(pub_year_match.group(0), "")
                full_search_text = full_search_text.strip().rstrip(',. ')
        # 1. Page Match
        pp_match = re.search(r'\b(?:pp?\.?|Pages?|Page\s*No\.?|頁)\s*(\d+(?:\s*(?:[\–\-—]|to)\s*\d+)?)', full_search_text, re.IGNORECASE)
        if not pp_match:
            # 尋找 "數字-數字" 結尾
            noprefix_pp_match = re.search(r'(?:,|^)\s*(\d{1,5}\s*[-–]\s*\d{1,5})\.?\s*$', full_search_text)
            if noprefix_pp_match:
                pp_match = noprefix_pp_match
                
        arxiv_match = re.search(r'arXiv\s*(?:preprint)?\s*(?:arXiv)?[:\s]*([\d\.]+)', full_search_text, re.IGNORECASE)
        
        if arxiv_match:
            arxiv_id = arxiv_match.group(1)
            result['source_type'] = 'Preprint/arXiv'
            # 將 arXiv 編號存入 url 或 report_number (視您的資料庫設計而定)
            # 建議轉為標準 URL
            result['url'] = f"https://arxiv.org/abs/{arxiv_id}"
            
            # 將 arXiv 字串從 source 中移除，避免被當成期刊名
            # 這裡使用替換法
            full_search_text = full_search_text.replace(arxiv_match.group(0), "").strip().strip(',. ')
            
            # 如果剩餘文字包含 "arXiv preprint"，也清理掉
            full_search_text = re.sub(r'arXiv\s*preprint', '', full_search_text, flags=re.IGNORECASE).strip().strip(',. ')
            
            # 設定 Source 為 "arXiv" (可選)
            if not result['source']:
                result['source'] = "arXiv"
        
        ssrn_match = re.search(r'SSRN\s+(\d+)', full_search_text, re.IGNORECASE)
        
        if ssrn_match:
            ssrn_id = ssrn_match.group(1)
            result['source_type'] = 'Working Paper/Preprint'
            result['report_number'] = f"SSRN {ssrn_id}"
            
            # 生成標準 SSRN URL
            result['url'] = f"https://papers.ssrn.com/sol3/papers.cfm?abstract_id={ssrn_id}"
            
            # 將 SSRN 相關字串從 source 中移除，避免被當成期刊名
            # 移除 "Available at SSRN 4658103" 或 "SSRN 4658103"
            full_search_text = re.sub(r'(?:Available\s+at\s+)?SSRN\s+' + ssrn_id, '', full_search_text, flags=re.IGNORECASE).strip().strip(',. ')
            
            # 如果 Source 只剩下空字串或雜訊，就將其清空，避免顯示 "at"
            if not full_search_text or re.match(r'^(at|in)\b', full_search_text, re.IGNORECASE):
                result['source'] = None
            else:
                result['source'] = full_search_text

        # 處理另一種 SSRN 寫法: "SSRN Electronic Journal"
        elif re.search(r'SSRN\s+Electronic\s+Journal', full_search_text, re.IGNORECASE):
            result['source_type'] = 'Journal Article'
            result['journal_name'] = "SSRN Electronic Journal"
            result['source'] = "SSRN Electronic Journal"

        if pp_match: 
            raw_pages = pp_match.group(1)
            result['pages'] = re.sub(r'\s+', '', raw_pages).replace('to', '-').replace('–', '-').replace('—', '-')
            
            # 使用位置截斷 (Slicing) 而非 replace
            # 將抓到的部分直接從字串中挖掉
            start, end = pp_match.span()
            full_search_text = full_search_text[:start] + " " + full_search_text[end:]
            
        # 2. Volume Match
        vol_match = re.search(r'\b(?:Vol\.?|Volume|卷|第\s*\d+\s*卷)\s*(\d+)', full_search_text, re.IGNORECASE)
        if not vol_match: vol_match = re.search(r'第\s*(\d+)\s*卷', full_search_text)
        if vol_match: result['volume'] = vol_match.group(1)
        
        # 3. Issue Match (加入 Negative Lookbehind 作為雙重保險)
        no_match = re.search(r'(?<!Page\s)\b(?:no\.?|期|第\s*\d+\s*期)\s*(\d+)', full_search_text, re.IGNORECASE)
        if not no_match: no_match = re.search(r'第\s*(\d+)\s*期', full_search_text)
        if no_match: result['issue'] = no_match.group(1)
        
        
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
            r'(?:,|^)\s*\d{1,4}\s*[-–]\s*\d{1,4}\.?\s*$', 
            r'doi:', 
            months_regex
        ]
        min_pos = len(full_search_text)
        
        for ind in end_indicators:
            matches = list(re.finditer(ind, full_search_text, re.IGNORECASE))
            for m in matches:
                if (r'19\d{2}' in ind or r'20\d{2}' in ind):
                    # 抓取前面的 context
                    pre_text = full_search_text[:m.start()].strip()
                    post_text = full_search_text[m.end():].strip()
                    if pre_text.endswith('(') and post_text.startswith(')'):
                        continue
                    
                    # 另一種情況：FG 2017 (沒有括號，但前面是字母且無逗號)
                    if re.search(r'[a-zA-Z]\s*$', pre_text) and not pre_text.endswith(','):
                        continue
                if (r'19\d{2}' in ind or r'20\d{2}' in ind):
                    context_after = full_search_text[m.end():]
                    if re.search(r'(卷|期|頁)', full_search_text[m.end():m.end()+5]): 
                        if m.start() < min_pos: min_pos = m.start()
                        continue
                    if m.start() < 5 and re.search(r'[a-zA-Z]', context_after): continue 
                    if re.search(r'\b(Conference|Symposium|Workshop|Congress|Meeting|Lecture Notes|Proceedings)\b', full_search_text[m.end():m.end()+60], re.IGNORECASE):
                        continue
                if m.start() < min_pos:
                # 如果切斷點是「月份」，往回檢查是否黏著日期數字 (如 19-20)
                # 判斷這個 match 是否來自月份 regex
                    is_month_match = re.search(months_regex, m.group(0), re.IGNORECASE)
                
                real_start = m.start()
                if is_month_match:
                    # 抓取月份前面的文字
                    prefix_text = full_search_text[:m.start()]
                    # 檢查結尾是否有 "19-20 " 或 "19 "
                    # 允許前面有逗號或空白
                    date_prefix = re.search(r'(?:^|[\s,])(\d{1,2}(?:[-–]\d{1,2})?)\s*$', prefix_text)
                    if date_prefix:
                        # 如果抓到前面的數字，將切斷點 (min_pos) 往前推到數字的開始位置
                        # date_prefix.start(1) 是群組 1 (數字部分) 在 prefix_text 中的起始位置
                        real_start = date_prefix.start(1)

                min_pos = real_start
                break
        
        source_candidate = full_search_text[:min_pos].strip().strip(',. -')
        clean_source = clean_source_text(source_candidate)
        if clean_source and not re.match(r'^(http|www)', clean_source, re.IGNORECASE):
            result['source'] = clean_source
        
        # Source Type
        if 'CoRR' in full_search_text or 'abs/' in full_search_text:
            result['source_type'] = 'Preprint/arXiv'
            
            # 嘗試抓取 abs/xxxx
            abs_match = re.search(r'abs/(\d{4}\.\d+)', full_search_text)
            if not abs_match:
                abs_match = re.search(r'abs/(\d+\.\d+)', full_search_text)

            if abs_match:
                arxiv_id = abs_match.group(1)
                
                # [修正] 即使原本有 URL，如果它是錯的 (例如結尾是 .)，我們也要覆蓋它
                current_url = result.get('url', '')
                if not current_url or current_url.endswith('.') or 'abs/.' in current_url:
                    result['url'] = f"https://arxiv.org/abs/{arxiv_id}"
                
                # 清理 source
                result['source'] = "CoRR" 
                
                # 重要：如果 Volume 被誤填為 abs/...，要清空
                if result.get('volume') and 'abs/' in str(result['volume']):
                    result['volume'] = None
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

        months_pattern = r'(?:' + '|'.join(months_list) + r')\.?'
        # 模式 1: 日-日 月, 年 (19-20 Nov., 2004)
        date_pattern1 = re.compile(r'\b(\d{1,2}(?:[-–]\d{1,2})?)\s+(' + months_pattern + r'),?\s*' + str(result['year']), re.IGNORECASE)
        
        # 模式 2: 月 日-日, 年 (March 16-18, 2004)
        date_pattern2 = re.compile(r'\b(' + months_pattern + r')\s+(\d{1,2}(?:[-–]\d{1,2})?),?\s*' + str(result['year']), re.IGNORECASE)

        # 使用 after_title 來搜尋月份，不要覆蓋 full_search_text
        temp_search_for_month = after_title

        # 嘗試匹配完整日期
        date_match = None
        if result['year']:
            date_match = date_pattern1.search(temp_search_for_month)
            if not date_match:
                date_match = date_pattern2.search(temp_search_for_month)
        if date_match:
            raw_date = date_match.group(0)
            result['month'] = raw_date.replace(str(result['year']), '').strip(',. ')
        else:
        # 只抓月份單字（同樣從 temp_search_for_month 搜尋）
            month_part = r'(?:' + '|'.join(months_list) + r')\.?'
            comp_month_match = re.search(r'\b' + month_part + r'\s*[-/–]\s*' + month_part + r'\b', temp_search_for_month, re.IGNORECASE)
            if comp_month_match:
                result['month'] = comp_month_match.group(0)
            else:
                month_match = re.search(months_regex, full_search_text, re.IGNORECASE)
                if month_match: result['month'] = month_match.group(0)
        
        # DOI
        doi_match = re.search(r'(?:doi:|DOI:|https?://doi\.org/)\s*(10\.\d{4,}/[^\s,;\]\)]+)', full_search_text)
        if doi_match: result['doi'] = doi_match.group(1).rstrip('.')
        
        # URL (如果之前在前面沒抓到，這裡做最後確認，但不覆蓋已抓到的完整 URL)
        if not result['url']:
            url_match = re.search(r'(https?://[^\s,;]+)', full_search_text, re.IGNORECASE)
            if url_match:
                # 檢查抓到的 URL 是否以點號結束，且後面還有 "com", "org" 等頂級域名
                raw_url = url_match.group(1)
                end_pos = url_match.end()

                # 偷看後面的文字，看是否有斷開的域名部分
                # 例如 raw_url="https://mathworld.", 後面是 " wolfram. com/"
                remaining = full_search_text[end_pos:]
            
                # 尋找斷裂的域名模式： (空格 + 單字 + 點/斜線)
                broken_domain_match = re.match(r'^((?:\s+[a-z0-9]+[\./])+(?:com|org|net|edu|gov)\b[^\s]*)', remaining, re.IGNORECASE)

                if broken_domain_match:
                    # 拼起來，並移除空格
                    full_broken_url = raw_url + broken_domain_match.group(1)
                    result['url'] = full_broken_url.replace(' ', '').replace('\n', '')
                else:
                    result['url'] = raw_url.rstrip('.,;)]')
            pdf_url_match = re.search(r'(?:Available:|Retrieved from|URL)\s*(https?://.*?\.pdf)', full_search_text, re.IGNORECASE)
            if pdf_url_match:
                result['url'] = pdf_url_match.group(1).strip()
            else:
                url_match = re.search(r'(?:Available:|Retrieved from|URL)\s*(https?://[^,\n\s\]\)]+)', full_search_text, re.IGNORECASE)
                if url_match:
                    # result['url'] = url_match.group(1).strip()
                    result['url'] = url_match.group(1).strip().rstrip('.,;)]')
                elif not result['url']:
                    gen_url = re.search(r'(https?://[^\s,;]+(?:\.pdf)?)', full_search_text, re.IGNORECASE)
                    if gen_url: result['url'] = gen_url.group(1).strip()

        if result['url'] and 'doi.org' in result['url'] and result['doi']: result['url'] = None
        if result['source'] and re.fullmatch(r'(URL|Available|Online|Retrieved|Website)', result['source'], re.IGNORECASE): result['source'] = None
        
        # Access Date
        acc_match = re.search(r'(?:accessed|retrieved|downloaded)\s+(?:on\s+)?([A-Za-z]+\.?\s+\d{1,2},?\s*\d{4})', full_search_text, re.IGNORECASE)
        if acc_match: result['access_date'] = acc_match.group(1)

        if result.get('source'):
            src = result['source']
            cut_indices = []

            def get_match_index(pattern):
                m = re.search(pattern, src, re.IGNORECASE)
                if m: return m.start()
                return None

            # 1. 檢查 Volume (e.g. "vol. 37")
            if result.get('volume'):
                p = r'(?:,\s*|\s+)(?:Vol\.?|Volume|卷)\s*' + re.escape(result['volume']) + r'\b'
                idx = get_match_index(p)
                if idx is not None: cut_indices.append(idx)

            # 2. 檢查 Issue (e.g. "no. 5")
            if result.get('issue'):
                p = r'(?:,\s*|\s+)(?:No\.?|Issue|Num|Number|期)\s*' + re.escape(result['issue']) + r'\b'
                idx = get_match_index(p)
                if idx is not None: cut_indices.append(idx)

            # 3. 檢查 Pages (以防 pp. 漏網)
            if result.get('pages'):
                start_page = result['pages'].split('-')[0]
                p = r'(?:,\s*|\s+)(?:pp\.?|Pages?|頁)\s*' + re.escape(start_page)
                idx = get_match_index(p)
                if idx is not None: cut_indices.append(idx)
            
            # 4. 檢查 Year (強制清除結尾年份)
            if result.get('year') and len(src) > 20: 
                p = r'(?:,\s*|\s+)' + re.escape(str(result['year'])) + r'\s*$'
                idx = get_match_index(p)
                if idx is not None and idx > 10: cut_indices.append(idx)
            # 5. 檢查殘留月份 (e.g. ", Sept")
            month_end_match = re.search(r'(?:,\s*|\s+)(' + months_regex + r')[\.\s]*$', src, re.IGNORECASE)
            if month_end_match:
                cut_indices.append(month_end_match.start())

            # 執行截斷
            if cut_indices:
                min_idx = min(cut_indices)
                src = src[:min_idx].strip().rstrip(',. -')
                result['source'] = src
            date_range_match = re.search(r'(?:,\s*|\s+)\d{1,2}(?:[-–]\d{1,2})?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*,?\s*\d{4}\s*$', src, re.IGNORECASE)
            
            if date_range_match:
                # 記錄這段日期，補回 result['month']
                raw_date = date_range_match.group(0).strip(',. ')
                if not result.get('month'):
                    month_in_date = re.search(r'[a-zA-Z]+', raw_date)
                    if month_in_date: result['month'] = month_in_date.group(0)

                # 執行切除
                src = src[:date_range_match.start()].strip().rstrip(',. -')

            # 2. 嘗試移除單純的「月份+年份」 (如 Oct. 2022)
            # 必須在字串尾端，且前面有逗號分隔
            elif re.search(r',\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*,?\s*\d{4}\s*$', src, re.IGNORECASE):
                month_year_match = re.search(r',\s+((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*,?\s*\d{4})\s*$', src, re.IGNORECASE)
                if month_year_match:
                    src = src[:month_year_match.start()].strip().rstrip(',. -')

            result['source'] = src
            
            # 同步更新 conference_name
            if result.get('source_type') == 'Conference Paper':
                result['conference_name'] = src
        # 比對 Source 與 Title
        if result.get('source') and result.get('title'):
            t_clean = re.sub(r'[\W_]+', '', result['title'].lower())
            s_clean = re.sub(r'[\W_]+', '', result['source'].lower())
            if t_clean == s_clean: result['source'] = None
            elif t_clean in s_clean and len(s_clean) - len(t_clean) < 15: result['source'] = None
            elif s_clean in t_clean: result['source'] = None

        if result.get('source'):
            # [優先檢查] 檢測並修復斷裂的 URL (wolfram. com)
            # 這是為了處理像 "mathworld. wolfram. com/" 這樣的案例
            if re.search(r'\b(?:com|org|net|edu|gov)\b', result['source'], re.IGNORECASE):
                # 嘗試移除所有空格
                temp_url = result['source'].replace(' ', '').replace('\n', '')
                # 檢查修復後是否像一個 URL (包含 .com/.org 等，且長度合理)
                if re.search(r'[\w\-\.]+\.(?:com|org|net|edu|gov)', temp_url, re.IGNORECASE):
                    # 如果原本沒有 URL，或者原本的 URL 殘缺不全，就採用這個
                    if not result.get('url') or len(result['url']) < 10:
                        if not temp_url.startswith('http'):
                            temp_url = "http://" + temp_url
                        result['url'] = temp_url
                        result['source'] = None # 清空 source，因為它其實是 URL
            
            # [修正] 只有當 Source 還存在時，才繼續執行後續的 URL 檢查
            if result.get('source'):
                looks_like_url = re.search(r'\.\s*(?:com|org|net|edu|gov|io)\b', result['source'], re.IGNORECASE)
                has_http = re.search(r'https?://', result['source'], re.IGNORECASE)
                has_www = re.search(r'www\.', result['source'], re.IGNORECASE)
                
                if looks_like_url or has_http or has_www:
                    # 只有當 result['url'] 還沒有值的時候，才把這個疑似網址的東西搬過去
                    # (但您的案例中已經有 https://mathworld... 了，所以這裡應該直接清空 Source)
                    if not result.get('url'):
                        # 嘗試修復空格 (如 "wolfram. com" -> "wolfram.com")
                        fixed_url = result['source'].replace('. ', '.')
                        if not fixed_url.startswith('http'):
                            fixed_url = "http://" + fixed_url
                        result['url'] = fixed_url
                    
                    # 清空誤判的 Source
                    result['source'] = None
                    
                    # 如果誤判為 Journal，也要清空
                    if result.get('journal_name') == result.get('source'):
                        result['journal_name'] = None

        # 重新檢查 full_search_text 來判斷類型
            if re.search(r'(Proc\.|Proceedings|Conference|Symposium|Workshop)', full_search_text, re.IGNORECASE):
                result['source_type'] = 'Conference Paper'
                result['conference_name'] = result['source']
            elif re.search(r'(vol\.|volume|no\.|number)', full_search_text, re.IGNORECASE):
                result['source_type'] = 'Journal Article'
                result['journal_name'] = result['source']
            elif re.search(r'(Ph\.D\.|M\.S\.|thesis)', full_search_text, re.IGNORECASE):
                result['source_type'] = 'Thesis/Dissertation'
            elif re.search(r'(Tech\. Rep\.|Technical Report)', full_search_text, re.IGNORECASE):
                result['source_type'] = 'Technical Report'
            elif re.search(r'Patent', full_search_text, re.IGNORECASE):
                result['source_type'] = 'Patent'
            elif re.search(r'\[Online\]|Available:|https?://|arxiv\.org', full_search_text, re.IGNORECASE):
                result['source_type'] = 'Website/Online'
            elif re.search(r'(Ed\.|Eds\.|edition)', full_search_text, re.IGNORECASE):
                result['source_type'] = 'Book'

    return result

def clean_source_text(text):
    if not text: return None
    
    text = re.sub(r'^in(?:[:\s]+|$)', '', text, flags=re.IGNORECASE)
    # [New] 移除 "presented at (the)"
    text = re.sub(r'^(?:presented|submitted)\s+at\s+(?:the\s+)?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^(?:presented|submitted)\s+to\s+(?:the\s+)?', '', text, flags=re.IGNORECASE)
    # [New] 移除 "Proceedings of (the)" (通常 Proc. 前面會有 in，但有時會連著 presented at)
    text = re.sub(r'^Pro[-\s]?ceedings\s+of\s+(?:the\s+)?', '', text, flags=re.IGNORECASE)
    # 1. 清理開頭的連接詞與標記 (in, 收錄於, J., [J] 等)
    text = re.sub(r'^(?:收錄於|載於|刊於)[:\s]*', '', text)
    text = re.sub(r'^J\.\s+', '', text)
    text = re.sub(r'\[[JCD]\]', '', text) # 移除 [J], [C], [D] 等分類標記
    # 2. 移除電子資源標記 ([Online], Available, Retrieved)
    text = re.sub(r'\[Online\]\.?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'Available:', '', text, flags=re.IGNORECASE)
    text = re.sub(r'Retrieved from', '', text, flags=re.IGNORECASE)
    # 3. 移除存取日期 (accessed ...)
    text = re.sub(r'\(?\s*accessed\.?.*', '', text, flags=re.IGNORECASE)
    # 4. 移除網址殘留 (https://...)
    text = re.sub(r'[,\s\-;，。、\.]+$', '', text) 
    # 5. 最終修剪標點與空白
    text = text.strip()

    # 3. 只清理結尾的「逗號、空格、破折號」，但保留句點（期刊縮寫需要）
    text = re.sub(r'[,\s\-;，。、\.]+$', '', text)
    return text

APA_INLINE_PATTERN = re.compile(
    r"""
    ^\s*                      # 開頭空白
    [^\.]+?                   # 先來一段「看起來像作者」的文字，不含句點
    \(\d{4}[a-z]?\)\.         # 接 (2018). 或 (2018a).
    """,
    re.VERBOSE
)

def looks_like_inline_apa(rest_text: str) -> bool:
    """
    去掉 [n] 後的文字，檢查是否為 APA inline：
    例：Hwang, G. H., Chen, P. H., ... (2018). InfiniteChain...
    """
    s = rest_text.strip()

    # 英文 APA：作者 + (年).
    if APA_INLINE_PATTERN.match(s):
        return True

    # 再補一個寬鬆版：作者, ... (年).
    loose = re.match(r'^[^\.]+?\(\d{4}[a-z]?\)\.', s)
    if loose:
        return True

    # 簡單中文 APA：作者（2018）。標題……
    if has_chinese(s) and re.search(r'（\s*\d{4}\s*）', s):
        # 要求年份括號出現在前半段，避免誤判正文
        if s.find('（') < 60:
            return True

    return False