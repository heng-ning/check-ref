import re
from utils.text_processor import (
    normalize_citation_for_matching,
    is_valid_year
)

def extract_in_text_citations(content_paragraphs, reference_list=None):
    """
    提取內文引用，APA 格式直接使用 reference_list 中已解析的 authors 和 year
    
    改進邏輯：
    - IEEE: 提取編號，再從 reference_list 查找對應的作者和年份
    - APA: 提取原始文本和年份，用年份反向匹配 reference_list，使用其標準化的作者和年份
    
    Args:
        content_paragraphs: 內文段落列表
        reference_list: 已解析的參考文獻列表（包含 authors, year, ref_number 等欄位）
    
    Returns:
        citations: 內文引用列表
    """
    full_text = " ".join(content_paragraphs)    
    
    # 1. 中文姓名（處理姓氏與名字分離的情況）
    #    例如: "葉 乃嘉(2013)" → "葉乃嘉(2013)"
    #    匹配: 單個中文字 + 多個空格 + 2-3個中文字 + (年份)
    full_text = re.sub(
        r'([\u4e00-\u9fff])\s+([\u4e00-\u9fff]{2,3})\s*[（(]\s*(\d{4}[a-z]?)\s*[）)]',
        r'\1\2(\3)',
        full_text
    )
    
    # 2. 中文姓名修復（處理「等人」前的斷裂）
    #    例如: "葉 乃嘉等人(2013)" → "葉乃嘉等人(2013)"
    full_text = re.sub(
        r'([\u4e00-\u9fff])\s+([\u4e00-\u9fff]{2,3}(?:等人?))\s*[（(]\s*(\d{4}[a-z]?)\s*[）)]',
        r'\1\2(\3)',
        full_text
    )
    
    # 3. 英文姓名修復
    #    例如: "Smith (2020)" → "Smith (2020)"（移除多餘空格）
    full_text = re.sub(
        r'([A-Z][a-z]+(?:\s+et\s+al\.?)?)\s+([（(]\s*\d{4}[a-z]?\s*[）)])',
        r'\1 \2',
        full_text
    )
    
    # 4. 清理多餘的連續空格（但保留單個空格）
    full_text = re.sub(r'  +', ' ', full_text)

    citations = []
    citation_ids = set()
    
    # 如果沒有提供 reference_list，建立空列表
    if reference_list is None:
        reference_list = []
    
    # --- 建立 reference_list 索引 ---
    ref_by_number = {}      # IEEE: {編號: ref_index}
    ref_by_year = {}        # APA: {年份: [ref_index列表]}
    ref_by_author_year = {} # APA精確匹配: {(標準化作者, 年份): ref_index}
    
    for i, ref in enumerate(reference_list):
        # IEEE 編號索引
        if ref.get('ref_number'):
            num = str(ref['ref_number']).strip()
            ref_by_number[num] = i
        
        # APA 年份索引
        year = _normalize_year(ref.get('year'))
        if year:
            if year not in ref_by_year:
                ref_by_year[year] = []
            ref_by_year[year].append(i)
            
            # 建立作者-年份精確索引
            authors = ref.get('authors') or ref.get('author')
            if authors:
                first_author_norm = _normalize_author_name(_get_first_author_str(authors))
                if first_author_norm:
                    key = (first_author_norm, year)
                    ref_by_author_year[key] = i
    
    # ==================== 提取內文引用 ====================
    
    # --- 1. APA 多引用: (作者1, 年份1; 作者2, 年份2; 作者3, 年份3...) ---
    # 明確匹配包含至少一個分號的情況，支持多個分號
    pattern_apa_multi = re.compile(
        r'[（(]\s*([^)）]+?(?:[;；][^)）]+?)+)\s*[）)]',
        re.UNICODE
    )
    for match in pattern_apa_multi.finditer(full_text):
        inner_text = match.group(1)
        # 用分號分割（支持中英文分號），可以處理多個分號的情況
        segments = re.split(r'\s*[;；]\s*', inner_text)
        
        if len(segments) > 1:
            citation_id_check = f"{match.start()}-{match.end()}"
            if citation_id_check in citation_ids:
                continue
                
            for idx, seg in enumerate(segments):
                seg_match = re.match(
                    r'([\w\s\u4e00-\u9fff&,、\-\.]+?(?:\s+(?:et\s*al\.?|等人?|等))?)\s*[,、]\s*(\d{4}[a-z]?)',
                    seg.strip()
                )
                if seg_match:
                    raw_author_part = seg_match.group(1).strip()  # 提取作者部分
                    raw_year = seg_match.group(2)[:4]
                    
                    if not raw_author_part.isdigit() and is_valid_year(raw_year):
                        citation_id = f"{match.start()}-multi-{idx}"
                        if citation_id not in citation_ids:
                            # 構造完整的引用格式，確保作者部分清晰
                            # 移除多餘空格（處理 "Angelini  et al." 這種情況）
                            raw_author_clean = re.sub(r'\s+', ' ', raw_author_part).strip()
                            seg_with_parens = f"({raw_author_clean}, {raw_year})"  # 改進格式
                            
                            matched_ref = _match_apa_citation_to_reference(
                                seg_with_parens, raw_year, ref_by_year, ref_by_author_year, reference_list
                            )
                            
                            normalized = normalize_citation_for_matching(seg.strip())
                            
                            citations.append({
                                'author': matched_ref['author'] if matched_ref else raw_author_clean,  # 使用清理後的作者
                                'co_author': None,
                                'year': matched_ref['year'] if matched_ref else raw_year,
                                'original': f"({seg.strip()})",
                                'normalized': normalized,
                                'position': match.start(),
                                'type': 'APA-parenthetical-multi',
                                'format': 'APA',
                                'matched_ref_index': matched_ref['index'] if matched_ref else None
                            })
                            citation_ids.add(citation_id)
    
    # --- 2. APA 單一括號式: (作者, 年份) 或 (作者 & 作者, 年份) 或 (作者、作者、作者, 年份) ---
    pattern_apa1 = re.compile(
        r'(?<![0-9])[（(]\s*'
        r'('  # group(1): 完整的作者部分
            r'[\w\s\u4e00-\u9fff&、\-\.,]+?'  # 允許逗號、& 和 、
            r'(?:\s+(?:et\s*al\.?|等人?|等))?'  # 可選的 et al.
        r')'
        r'\s*[,，]\s*'
        r'(\d{4}[a-z]?)'  # group(2): 年份
        r'(?:\s*[,，]?\s*pp?\.?\s*\d+(?:[-–—]\d+)?)?'  # 可選的頁碼：, p654 或 pp. 123-145
        r'\s*[）)]',
        re.UNICODE | re.IGNORECASE
    )

    for match in pattern_apa1.finditer(full_text):
        citation_id = f"{match.start()}-{match.end()}"
        if citation_id in citation_ids:
            continue
        
        raw_text = match.group(0)
        raw_author_text = match.group(1).strip()  # 完整的作者文本
        raw_year = match.group(2)[:4]
        
        # 檢查是否為純數字（避免誤匹配）
        if raw_author_text.isdigit():
            continue
        
        if is_valid_year(raw_year):
            # 清理並標準化作者分隔符
            raw_text_cleaned = raw_text

            # 分析作者部分（移除年份括號）
            author_part_match = re.match(r'[（(]\s*(.+?)\s*[,，]\s*\d{4}[a-z]?\s*[）)]', raw_text_cleaned, re.DOTALL)
            if author_part_match:
                author_part = author_part_match.group(1)  # 只提取作者部分
                
                # 先標準化：將逗號後無空格的情況補上空格（例如 "A,B" → "A, B"）
                author_part_normalized = re.sub(r',(?!\s)', ', ', author_part)
                
                # 統計逗號數量和是否有連接詞
                comma_count = author_part_normalized.count(',')
                has_ampersand = '&' in author_part_normalized or ' and ' in author_part_normalized.lower()
                
                # 判斷作者數量並標準化
                # 特殊處理：如果有 &，檢查 & 兩邊是否都有作者
                if has_ampersand:
                    # 按 & 分割，檢查兩邊
                    parts = re.split(r'\s*&\s*', author_part_normalized)
                    if len(parts) == 2:
                        # 檢查每一邊有幾個作者（用逗號分割）
                        left_authors = [a.strip() for a in parts[0].split(',') if a.strip()]
                        right_authors = [a.strip() for a in parts[1].split(',') if a.strip()]
                        total_authors = len(left_authors) + len(right_authors)
                        
                        if total_authors >= 3:
                            # 三作者或更多
                            raw_text_cleaned = re.sub(r',\s*&\s*', '、', raw_text_cleaned)
                            raw_text_cleaned = re.sub(r'\s+&\s+', '、', raw_text_cleaned)
                            raw_text_cleaned = re.sub(r',\s*(?=[A-Za-z\u4e00-\u9fff])', '、', raw_text_cleaned)
                        else:
                            # 雙作者
                            raw_text_cleaned = re.sub(r',\s*&\s*', ' & ', raw_text_cleaned)
                            raw_text_cleaned = re.sub(r',(?=\w)', ', ', raw_text_cleaned)
                elif comma_count >= 2:
                    # 沒有 &，但有 2+ 個逗號 → 三作者
                    raw_text_cleaned = re.sub(r',\s*(?=[A-Za-z\u4e00-\u9fff])', '、', raw_text_cleaned)
                elif ' and ' in raw_text_cleaned.lower():
                    # 英文 "and" 連接
                    raw_text_cleaned = re.sub(r'\s+and\s+', ' & ', raw_text_cleaned, flags=re.IGNORECASE)

            # 用年份和原始文本反向匹配 reference_list
            matched_ref = _match_apa_citation_to_reference(
                raw_text_cleaned, raw_year, ref_by_year, ref_by_author_year, reference_list
            )
            
            normalized = normalize_citation_for_matching(match.group(0))
            
            citations.append({
                'author': matched_ref['author'] if matched_ref else raw_author_text,
                'co_author': None,  # 移除 co_author（不再單獨提取）
                'year': matched_ref['year'] if matched_ref else raw_year,
                'original': match.group(0),
                'normalized': normalized,
                'position': match.start(),
                'type': 'APA-parenthetical',
                'format': 'APA',
                'matched_ref_index': matched_ref['index'] if matched_ref else None
            })
            citation_ids.add(citation_id)

    # --- 3. APA 敘述式: 作者 (年份) ---
    pattern_apa2 = re.compile(
        r'(?<![0-9])'  # 前面不能是數字
        r'('  # group(1): 作者部分
            # 中文作者（2-4個中文字 + 可選的等/等人）
            r'(?:[\u4e00-\u9fff]{2,4}(?:等人?|等)?)|'
            # 英文作者/機構（支持連字符、撇號，以及逗號分隔的 et al.）
            r'(?:[A-Za-z\-\']+(?:\s+[A-Za-z\-\']+){0,4}(?:[\s,]+(?:et\s*al\.?|等人?|等))?)'
        r')'
        # 匹配「等人」之後可能出現的連接詞（則表示、指出、發現等）
        r'(?:則表示|指出|發現|認為|提出|表示|指明|顯示|說明|強調|建議)?'
        # 可選的多作者連接（雙作者或三作者）
        r'(?:'
            # 雙作者:與/和/&/and + 第二作者
            r'(?:\s*(?:與|和|&|and)\s*'
                r'(?:'
                    r'(?:[\u4e00-\u9fff]{2,4})|'  # 中文第二作者
                    r'(?:[A-Za-z\-\']+(?:\s+[A-Za-z\-\']+){0,4})'  # 英文第二作者
                r')'
            r')|'
            # 三作者:、第二作者、第三作者（中文頓號連接）
            r'(?:、[\u4e00-\u9fff]{2,4}、[\u4e00-\u9fff]{2,4})'
        r')?'
        r'\s*[（(]\s*'
        r'(\d{4}[a-z]?)'  # group(2): 年份
        r'(?:\s*[,，]?\s*pp?\.?\s*\d+(?:[-–—]\d+)?)?'  # 可選的頁碼
        r'\s*[）)]',
        re.UNICODE | re.IGNORECASE
    )

    for match in pattern_apa2.finditer(full_text):
        raw_text = match.group(0)
        raw_year = match.group(2)[:4]
        
        # 先提取完整的匹配文本（包含可能的前綴）
        full_match_text = match.group(1).strip()
        
        if full_match_text.isdigit():
            continue
        
        # 過濾非作者名的中文詞彙
        non_author_keywords = [
            '檢定', '分析', '模型', '理論', '方法', '測試', '迴歸', '相關', 
            '整合', '驗證', '評估', '估計', '預測', '探討', '統計', '計算',
            '因素', '效應', '變數', '指標', '量表', '問卷', '研究', '調查'
        ]
        
        if any('\u4e00' <= c <= '\u9fff' for c in full_match_text):
            if any(keyword in full_match_text for keyword in non_author_keywords):
                continue
        
        # 如果同時包含英文和中文，優先提取英文部分
        if re.search(r'[A-Za-z]', full_match_text) and re.search(r'[\u4e00-\u9fff]', full_match_text):
            english_part = re.search(r'([A-Za-z\-\']+(?:\s+[A-Za-z\-\']+)*)', full_match_text)
            if english_part:
                full_match_text = english_part.group(1).strip()
                # 同時更新 raw_text 以便後續匹配
                raw_text = f"{full_match_text} ({raw_year})"
        
        if is_valid_year(raw_year):
            citation_id = f"{match.start()}-{match.end()}"
            if citation_id not in citation_ids:
                # 用年份和原始文本反向匹配 reference_list
                matched_ref = _match_apa_citation_to_reference(
                    raw_text, raw_year, ref_by_year, ref_by_author_year, reference_list
                )
                
                normalized = normalize_citation_for_matching(match.group(0))
                
                # 如果有匹配到 reference，使用其標準化的作者
                if matched_ref:
                    final_author = matched_ref['author']
                    
                    # 直接使用 parsed_authors 獲取姓氏
                    original_clean = match.group(0)
                    matched_ref_data = reference_list[matched_ref['index']]

                    # 檢查是否需要補全作者名
                    ref_full_author = matched_ref_data.get('authors')
                    if ref_full_author:
                        if isinstance(ref_full_author, list) and ref_full_author:
                            ref_first_author_full = ref_full_author[0]
                        else:
                            ref_first_author_full = str(ref_full_author)
                        
                        citation_author_part = re.search(r'^(.*?)\s*[（(]\s*\d{4}', original_clean)
                        if citation_author_part:
                            citation_author = citation_author_part.group(1).strip()
                            
                            # 判斷是中文還是英文，使用不同的比對邏輯
                            is_substring = False
                            if any('\u4e00' <= c <= '\u9fff' for c in citation_author):
                                # 中文：直接檢查子字串
                                is_substring = (len(citation_author) >= 3 and 
                                            citation_author in ref_first_author_full and
                                            citation_author != ref_first_author_full)
                            else:
                                # 英文：不區分大小寫
                                is_substring = (len(citation_author) >= 3 and 
                                            citation_author.lower() in ref_first_author_full.lower() and
                                            citation_author.lower() != ref_first_author_full.lower())

                            if is_substring:
                                year_part = re.search(r'[（(]\s*\d{4}[a-z]?(?:\s*[,，]?\s*pp?\.?\s*\d+(?:[-–—]\d+)?)?\s*[）)]', original_clean)
                                if year_part:
                                    original_clean = f"{ref_first_author_full} {year_part.group(0)}"

                    parsed_authors = matched_ref_data.get('parsed_authors')
                    
                    if parsed_authors and isinstance(parsed_authors, list):
                        author_count = len(parsed_authors)
                        
                        # 檢查哪些作者出現在原文中
                        found_authors = []
                        for i, author_info in enumerate(parsed_authors):
                            surname = author_info.get('last', '')
                            if surname and surname in original_clean:
                                found_authors.append(i)
                        
                        # 如果是雙作者，但只找到第二作者，重建完整格式
                        if author_count == 2 and found_authors == [1]:
                            # 只有第二作者出現 → 重建為 "第一作者 連接詞 第二作者 (年份)"
                            first_surname = parsed_authors[0].get('last', '')
                            second_surname = parsed_authors[1].get('last', '')
                            
                            # 檢測原文使用的連接詞
                            if '與' in original_clean or '和' in original_clean:
                                connector = '與' if '與' in original_clean else '和'
                            else:
                                connector = ' and '  # 英文預設用 and
                            
                            # 提取年份部分
                            year_match = re.search(r'\((\d{4}[a-z]?)\)', original_clean)
                            if year_match:
                                year_part = year_match.group(0)
                                original_clean = f"{first_surname} {connector} {second_surname} {year_part}"
                        else:
                            # 其他情況：找到最早出現的作者位置並截取
                            earliest_pos = len(original_clean)
                            for author_info in parsed_authors:
                                surname = author_info.get('last', '')
                                if surname:
                                    surname_pos = original_clean.find(surname)
                                    if surname_pos != -1:
                                        earliest_pos = min(earliest_pos, surname_pos)
                            
                            if earliest_pos < len(original_clean) and earliest_pos > 0:
                                original_clean = original_clean[earliest_pos:]
                    else:
                        # 沒有 parsed_authors，使用 authors 欄位（中文參考文獻或其他格式）
                        ref_authors = matched_ref_data.get('authors')
                        if ref_authors and isinstance(ref_authors, list):
                            author_count = len(ref_authors)
                            
                            # 檢查哪些作者出現在原文中
                            found_authors = []
                            for i, author_name in enumerate(ref_authors):
                                if author_name and author_name in original_clean:
                                    found_authors.append(i)
                                else:
                                    # 中文作者：檢查名字部分（去掉姓氏）
                                    if any('\u4e00' <= c <= '\u9fff' for c in author_name) and len(author_name) >= 2:
                                        given_name = author_name[1:]  # 去掉第一個字（姓氏）
                                        if given_name and given_name in original_clean:
                                            found_authors.append(i)
                            
                            # 如果是雙作者，但只找到第二作者，重建完整格式
                            if author_count == 2 and found_authors == [1]:
                                # 只有第二作者出現 → 重建為 "第一作者 連接詞 第二作者 (年份)"
                                first_author_name = ref_authors[0]
                                second_author_name = ref_authors[1]
                                
                                # 檢測原文使用的連接詞（如果有的話）
                                connector = ' 與 '  # 預設使用中文連接詞
                                
                                # 提取年份部分
                                year_match = re.search(r'\((\d{4}[a-z]?)\)', original_clean)
                                if year_match:
                                    year_part = year_match.group(0)
                                    original_clean = f"{first_author_name}{connector}{second_author_name} {year_part}"
                            else:
                                # 其他情況：找到最早出現的作者位置並截取
                                earliest_pos = len(original_clean)
                                for author_name in ref_authors:
                                    author_pos = original_clean.find(author_name)
                                    if author_pos != -1:
                                        earliest_pos = min(earliest_pos, author_pos)
                                    else:
                                        # 中文作者：檢查名字部分
                                        if any('\u4e00' <= c <= '\u9fff' for c in author_name) and len(author_name) >= 2:
                                            given_name = author_name[1:]
                                            given_name_pos = original_clean.find(given_name)
                                            if given_name_pos != -1:
                                                earliest_pos = min(earliest_pos, given_name_pos)
                                
                                # 從最早的作者位置開始截取
                                if earliest_pos < len(original_clean) and earliest_pos > 0:
                                    original_clean = original_clean[earliest_pos:]
                else:
                    # 沒有匹配到，嘗試清理雜訊前綴
                    final_author = _clean_author_prefix(full_match_text)
                    original_clean = match.group(0)
                    
                    # 檢查是否有雙作者連接詞
                    connectors = ['與', '和', '&', ' and ']
                    for connector in connectors:
                        conn_pos = original_clean.find(connector)
                        if conn_pos != -1:
                            # 找到連接詞
                            before_connector = original_clean[:conn_pos]
                            after_connector = original_clean[conn_pos + len(connector):].lstrip()
                            
                            # 檢查連接詞後面是否有作者名
                            if after_connector and any(c.isalpha() for c in after_connector):
                                # 判斷連接詞前面是否有有效的作者名
                                if conn_pos <= 1 or not any(c.isalnum() or '\u4e00' <= c <= '\u9fff' for c in before_connector):
                                    # 連接詞前面沒有有效內容，只保留連接詞後面的部分
                                    original_clean = after_connector
                                else:
                                    # 連接詞前面有內容，嘗試提取第一作者
                                    is_chinese = any('\u4e00' <= c <= '\u9fff' for c in after_connector)
                                    
                                    if is_chinese:
                                        # 中文：往前截取中文字，但過濾非人名字
                                        chinese_chars = []
                                        # 常見的非人名字（通常出現在句子或文章標題中）
                                        non_name_chars = set('的之與和及或而且但然後因為所以等於對於關於根據依據參考'
                                                        '本研究文章論述結果發現指出認為顯示表示分析探討'
                                                        '以從在於當若如由至從到')
                                        
                                        for i in range(conn_pos - 1, -1, -1):
                                            char = before_connector[i]
                                            if '\u4e00' <= char <= '\u9fff':
                                                # 檢查是否為非人名字
                                                if char in non_name_chars:
                                                    # 遇到非人名字，停止收集
                                                    break
                                                chinese_chars.insert(0, char)
                                                if len(chinese_chars) >= 4:
                                                    # 人名通常不超過 4 個字
                                                    break
                                            elif chinese_chars:
                                                # 遇到非中文字符且已經收集到中文字，停止
                                                break
                                        
                                        # 只有收集到 2-4 個字才算有效人名
                                        if 2 <= len(chinese_chars) <= 4:
                                            first_author = ''.join(chinese_chars)
                                            original_clean = f"{first_author}{connector}{after_connector}"
                                        else:
                                            # 找不到有效人名，只保留連接詞後面的部分
                                            original_clean = after_connector
                                    else:
                                        # 英文：往前截取一個單詞（姓氏）
                                        words_before = before_connector.rstrip().split()
                                        if words_before:
                                            first_author_surname = words_before[-1]
                                            if len(first_author_surname) >= 2 and first_author_surname.isalpha():
                                                original_clean = f"{first_author_surname}{connector}{after_connector}"
                                            else:
                                                original_clean = after_connector
                                        else:
                                            original_clean = after_connector
                                
                                break

                # 清理 original_clean：移除「等人」之後的連接詞
                if '等人' in original_clean:
                    # 使用正則表達式移除「等人」後的連接詞（則表示、指出、發現等）
                    original_clean = re.sub(
                        r'(等人)(?:則表示|指出|發現|認為|提出|表示|指明|顯示|說明|強調|建議)',
                        r'\1',  # 只保留「等人」
                        original_clean
                    )

                citations.append({
                    'author': final_author,
                    'co_author': None,
                    'year': matched_ref['year'] if matched_ref else raw_year,
                    'original': original_clean,  # 使用清理後的文本
                    'normalized': normalize_citation_for_matching(original_clean),
                    'position': match.start(),
                    'type': 'APA-narrative',
                    'format': 'APA',
                    'matched_ref_index': matched_ref['index'] if matched_ref else None
                })
                citation_ids.add(citation_id)
    
    # --- 4. IEEE 數字式範圍: [n]-[m] ---
    pattern_ieee_range_brackets = re.compile(
        r'([【\[]\s*\d+\s*[】\]])\s*[–\-\—~～]\s*([【\[]\s*\d+\s*[】\]])',
        re.UNICODE
    )
    for match in pattern_ieee_range_brackets.finditer(full_text):
        start_bracket = match.group(1)
        end_bracket = match.group(2)
        
        start_n = int(re.search(r'\d+', start_bracket).group(0))
        end_n = int(re.search(r'\d+', end_bracket).group(0))
        
        if start_n == 0 or end_n == 0:
            continue

        extracted_numbers = []
        
        if start_n < end_n and (end_n - start_n) < 100:
            for k in range(start_n, end_n + 1):
                extracted_numbers.append(str(k))
        
        final_numbers = []
        for num in extracted_numbers:
            val = int(num)
            if val == 0 or val > 2000:
                continue
            final_numbers.append(str(val))
            
        if not final_numbers:
            continue

        citation_id = f"{match.start()}-{match.end()}"
        if citation_id not in citation_ids:
            normalized = normalize_citation_for_matching(match.group(0))
            
            # 從 reference_list 查找第一個編號對應的作者和年份
            first_num = final_numbers[0]
            if first_num in ref_by_number:
                matched_ref = reference_list[ref_by_number[first_num]]
                std_authors = matched_ref.get('authors') or matched_ref.get('author')
                std_year = matched_ref.get('year')
                matched_index = ref_by_number[first_num]
            else:
                std_authors = None
                std_year = None
                matched_index = None
            
            citations.append({
                'author': _get_first_author_str(std_authors) if std_authors else None,
                'co_author': None,
                'year': std_year,
                'ref_number': final_numbers[0], 
                'all_numbers': final_numbers,
                'original': match.group(0),
                'normalized': normalized,
                'position': match.start(),
                'type': 'IEEE-numeric-range',
                'format': 'IEEE',
                'matched_ref_index': matched_index
            })
            citation_ids.add(citation_id)
    
    # --- 5. IEEE 數字式: [n] 或 [n,m,k] ---
    pattern_ieee_robust = re.compile(
        r'[【\[]\s*(\d+(?:[–\-\—~～,;\s]+\d+)*)\s*[】\]]', 
        re.UNICODE
    )

    for match in pattern_ieee_robust.finditer(full_text):
        content_str = match.group(1)
        if re.match(r'^0\b', content_str) or re.search(r'[,;]\s*0\b', content_str):
            continue
            
        raw_parts = re.split(r'\s*[,;]\s*', content_str)
        temp_numbers = []
        
        for part in raw_parts:
            part = part.strip()
            range_match = re.match(r'(\d+)\s*[–\-\—~～]\s*(\d+)', part)
            if range_match:
                start_n = int(range_match.group(1))
                end_n = int(range_match.group(2))
                if start_n == 0 or end_n == 0:
                    continue
                if start_n < end_n and (end_n - start_n) < 100:
                    for k in range(start_n, end_n + 1):
                        temp_numbers.append(str(k))
            elif part.isdigit():
                temp_numbers.append(part)
        
        extracted_numbers = []
        for num in temp_numbers:
            val = int(num)
            if val == 0 or val > 2000:
                continue
            if num.startswith('0') and len(num) > 1:
                continue
            extracted_numbers.append(str(val))

        if not extracted_numbers:
            continue
        
        # 檢查是否至少有一個編號在參考文獻中存在
        if reference_list:
            has_valid_ref = any(n in ref_by_number for n in extracted_numbers)
            if not has_valid_ref:
                # 所有編號都找不到 → 可能是數據，跳過
                continue

        citation_id = f"{match.start()}-{match.end()}"
        if citation_id not in citation_ids:
            normalized = normalize_citation_for_matching(match.group(0))
            
            # 從 reference_list 查找第一個編號對應的作者和年份
            first_num = extracted_numbers[0]
            if first_num in ref_by_number:
                matched_ref = reference_list[ref_by_number[first_num]]
                std_authors = matched_ref.get('authors') or matched_ref.get('author')
                std_year = matched_ref.get('year')
                matched_index = ref_by_number[first_num]
            else:
                std_authors = None
                std_year = None
                matched_index = None
            
            citations.append({
                'author': _get_first_author_str(std_authors) if std_authors else None,
                'co_author': None,
                'year': std_year,
                'ref_number': extracted_numbers[0], 
                'all_numbers': extracted_numbers,
                'original': match.group(0),
                'normalized': normalized,
                'position': match.start(),
                'type': 'IEEE-numeric',
                'format': 'IEEE',
                'matched_ref_index': matched_index
            })
            citation_ids.add(citation_id)
            
    return citations

def _normalize_author_name(author):
    """標準化作者姓名以便比對"""
    if not author:
        return ""
    
    author_str = str(author).lower()
    
    # 先將頓號替換為空格（避免作者名粘在一起）
    author_str = author_str.replace('、', ' ')
    
    # 移除常見綴詞
    for junk in ['et al.', 'et al', 'and', '&', ',', '與', '和', '及', '等人', '等', '.']:
        author_str = author_str.replace(junk, ' ')
    
    # 清理多余空格
    author_str = re.sub(r'\s+', ' ', author_str).strip()
    
    # 提取核心姓名
    if any('\u4e00' <= char <= '\u9fff' for char in author_str):
        # 中文作者
        core = "".join(filter(lambda c: c.isalnum() or '\u4e00' <= c <= '\u9fff', author_str))
    else:
        # 英文作者：取第一個單詞
        parts = author_str.split()
        if parts:
            core = "".join(filter(lambda c: c.isalnum() or c in '-\'', parts[0]))
        else:
            core = ""
    
    return core.strip()

def _normalize_year(year):
    """標準化年份"""
    if not year:
        return ""
    
    year_str = str(year)
    digits = ''.join(filter(str.isdigit, year_str))
    
    year_match = re.search(r'(19\d{2}|20\d{2})', digits)
    if year_match:
        return year_match.group(1)
    
    return digits[:4] if len(digits) >= 4 else digits


def _get_first_author_str(authors):
    """從 authors 資料中提取第一作者字串"""
    if not authors:
        return None
    
    if isinstance(authors, list):
        return authors[0] if authors else None
    
    return str(authors)

def _clean_author_prefix(author_text):
    """清理作者名前的中文雜訊前綴(僅在無法匹配 reference 時使用)"""
    junk_prefixes = [
        '本研究不僅再次驗證', '這些觀點皆與', '本研究採用', '此點亦與','等人則表示', 
        '而這與', '本研究', '也支持', '而在與', '這顯示',
        '根據', '依據', '參見', '參照', '此與', '亦與', '而這',
        '顯示', '指出', '發現', '認為', '以及', '至於', '反觀','結合',
        '如', '由', '採', '而', '與', '和', '及', '對', '故', 
        '經', '至', '則', '並', '但', '這', '其中'
    ]
    
    clean_author = author_text
    keep_cleaning = True
    while keep_cleaning:
        keep_cleaning = False
        for prefix in junk_prefixes:
            if clean_author.startswith(prefix):
                if len(clean_author) > len(prefix):
                    clean_author = clean_author[len(prefix):].strip()
                    keep_cleaning = True 
                break
    
    # 如果包含「等人」,移除「等人」之後到年份之前的所有文字
    # 例如:「等人則表示」→「等人」、「等人指出」→「等人」
    if '等人' in clean_author:
        # 找到「等人」的位置
        dengren_pos = clean_author.find('等人')
        if dengren_pos != -1:
            # 保留「等人」及之前的內容,移除「等人」之後的文字
            clean_author = clean_author[:dengren_pos + 2]  # +2 保留「等人」兩個字
    
    return clean_author

def _match_apa_citation_to_reference(raw_text, raw_year, ref_by_year, ref_by_author_year, reference_list):
    """
    將 APA 格式的內文引用反向匹配到 reference_list
    
    匹配策略：
    1. 先用年份縮小範圍
    2. 檢查內文引用的作者數量格式（單作者、雙作者、三作者、et al.、機構）
    3. 在該年份的所有 references 中，找符合作者數量規則且作者名匹配的
    4. 支援第二作者和第三作者匹配
    
    APA 作者數量規則：
    - 1 位作者: (Smith, 2020) or Smith (2020)
    - 2 位作者: (Smith & Jones, 2020) or Smith and Jones (2020)
    - 3 位作者: (莊懿妃、蔡義清、俞洪亮, 2018)
    - 3+ 位作者: (Smith et al., 2020) or Smith et al. (2020)
    - 團體/機構: (National Institute, 2020) or National Institute (2020)
    
    Args:
        raw_text: 原始引用文本，例如 "其中Garrett (2002)" 或 "(Smith & Jones, 2020)" 或 "志富 (2014)"
        raw_year: 提取的年份，例如 "2002"
        ref_by_year: 年份索引字典
        ref_by_author_year: 作者-年份精確索引
        reference_list: 完整的參考文獻列表
    
    Returns:
        匹配結果字典 {'author': str, 'year': str, 'index': int} 或 None
    """
    norm_year = _normalize_year(raw_year)
    if not norm_year:
        return None
    
    # 標準化原始文本（用於作者名比對）
    raw_text_lower = raw_text.lower()
    
    # 用年份縮小範圍
    if norm_year not in ref_by_year:
        return None
    
    candidate_indices = ref_by_year[norm_year]
    
    # ===== 判斷內文引用的作者數量類型 =====
    citation_type = _detect_citation_author_type(raw_text_lower)
    
    # 遍歷該年份的所有 references，找作者名和數量都匹配的
    best_match = None
    best_match_score = 0
    
    for ref_idx in candidate_indices:
        ref = reference_list[ref_idx]
        authors = ref.get('authors') or ref.get('author')
        
        if not authors:
            continue
        
        # 計算 reference 的作者數量
        if isinstance(authors, list):
            author_count = len(authors)
        else:
            # 字串格式，嘗試拆分（以逗號、分號、"and"、"&" 等分隔）
            author_str = str(authors)
            # 簡單計數：看有幾個常見的作者分隔符
            separators = [',', ';', ' and ', ' & ', '、', '與']
            author_count = 1
            for sep in separators:
                if sep in author_str:
                    author_count = len(re.split(r'[,;]|\sand\s|\s&\s|、|與', author_str))
                    break
        
        # 檢查參考文獻原文中是否有 et al.
        ref_original = ref.get('original', '')
        has_et_al_in_ref = bool(re.search(r'et\s*al\.?', ref_original, re.IGNORECASE))

        # 重新判斷作者數量（考慮 et al.）
        if has_et_al_in_ref and author_count == 1:
            author_count = 2  # 視為多作者（至少2位）

        # ===== 根據作者數量檢查是否匹配 =====
        is_count_match = False

        if citation_type == 'et_al':
            # 內文是 "et al." 格式
            # 如果參考文獻原文也有 "et al."，則無論 authors 列表有幾位，都視為匹配
            # 如果參考文獻沒有 "et al."，則要求至少 2 位作者
            if has_et_al_in_ref:
                is_count_match = True  # 參考文獻也用 et al.，直接匹配
            else:
                is_count_match = (author_count >= 2)  # 參考文獻沒用 et al.，要求至少 2 位
        elif citation_type == 'three_authors':
            # 內文是三作者格式 → reference 必須正好 3 位作者
            is_count_match = (author_count == 3)
        elif citation_type == 'two_authors':
            # 內文是 "A & B" 或 "A and B" → reference 必須正好 2 位作者
            is_count_match = (author_count == 2)
        elif citation_type == 'single_author':
            # 內文是單一作者 → 允許匹配任意數量的作者（可能是 PDF 截斷或只寫了部分名字）
            is_count_match = True
        elif citation_type == 'organization':
            # 內文是機構名稱 → 通常 reference 也是單一機構名（算 1 位）
            is_count_match = (author_count == 1)

        if not is_count_match:
            continue  # 作者數量不符，跳過
        
        # ===== 檢查作者名是否匹配 =====
        first_author = _get_first_author_str(authors)
        is_author_match = False
        match_score = 0

        # 檢查參考文獻原文中是否有 et al.
        # 如果有，即使 authors 只有 1 位，也視為多作者文獻
        ref_original = ref.get('original', '')
        has_et_al_in_ref = bool(re.search(r'et\s*al\.?', ref_original, re.IGNORECASE))

        # 重新判斷作者數量（考慮 et al.）
        if has_et_al_in_ref and author_count == 1:
            author_count = 2  # 視為多作者（至少2位）

        is_count_match = False

        # --- 先檢查第一作者 ---
        if first_author:
            # 如果 et al. 精確匹配失敗，或不是 et al. 格式，繼續其他匹配方法
            if not is_author_match:
                # 標準化作者名
                author_norm = _normalize_author_name(first_author)
                
                # 方法1:標準化後的作者名是否出現在原始引用文本中
                if author_norm:
                    # 移除 et al. 等干擾詞後再比對
                    citation_text_clean = re.sub(r'\s*et\s*al\.?|\s*等人', '', raw_text_lower)
                    if author_norm in citation_text_clean:
                        is_author_match = True
                        match_score = len(author_norm)
                        
                        # 如果是 et al. 格式且精確匹配第一作者姓氏,給予更高分數
                        if citation_type == 'et_al':
                            match_score += 1000
                
                # 方法1.5：反向匹配
                if not is_author_match:
                    citation_author_match = re.search(r'([A-Za-z\s\-\']+)\s*[（(]\s*\d{4}', raw_text_lower)
                    if citation_author_match:
                        citation_author = citation_author_match.group(1).strip()
                        citation_author = re.sub(r'^(the|a|an)\s+', '', citation_author, flags=re.IGNORECASE)
                        
                        if len(citation_author) >= 3 and citation_author in first_author.lower():
                            is_author_match = True
                            match_score = len(citation_author)
                
                # 方法2：提取姓氏部分（支援中英文）
                if not is_author_match:
                    if any('\u4e00' <= char <= '\u9fff' for char in first_author):
                        # 中文姓名處理
                        surname = first_author[0] if first_author else ''
                        
                        if len(first_author) >= 2:
                            given_name = first_author[1:] if len(first_author) > 1 else ''
                            if given_name and given_name in raw_text_lower:
                                is_author_match = True
                                match_score = len(given_name)

                        # 中文部分匹配
                        if not is_author_match:
                            citation_zh_match = re.search(r'([\u4e00-\u9fff]{2,})\s*[（(]\s*\d{4}', raw_text_lower)
                            if citation_zh_match:
                                citation_zh_author = citation_zh_match.group(1)
                                if len(citation_zh_author) >= 3 and citation_zh_author in first_author:
                                    is_author_match = True
                                    match_score = len(citation_zh_author)
                    else:
                        # 英文姓名：取姓氏
                        parts = first_author.split(',')
                        if len(parts) >= 1:
                            surname = parts[0].strip().lower()
                        else:
                            words = first_author.split()
                            surname = words[-1].lower() if words else ''

                        # 檢查姓氏是否出現在原始引用文本中
                        if not is_author_match and surname and surname in raw_text_lower:
                            surname_escaped = re.escape(surname)
                            surname_pattern = r'(?<![A-Za-z])' + surname_escaped + r'(?![A-Za-z])'
                            if re.search(surname_pattern, raw_text_lower, re.IGNORECASE):
                                is_author_match = True
                                match_score = len(surname)
                                
                                # 如果是 et al. 格式,額外加分
                                if citation_type == 'et_al':
                                    match_score += 500

                    # 檢查姓氏是否出現在原始引用文本中
                    if not is_author_match and surname and surname in raw_text_lower:
                        surname_escaped = re.escape(surname)
                        surname_pattern = r'(?<![A-Za-z])' + surname_escaped + r'(?![A-Za-z])'
                        if re.search(surname_pattern, raw_text_lower, re.IGNORECASE):
                            is_author_match = True
                            match_score = len(surname)
                            
                            # 精確匹配加分
                            citation_first_word_match = re.search(r'([A-Za-z\-\']+)', raw_text_lower)
                            if citation_first_word_match:
                                first_word = citation_first_word_match.group(1).strip()
                                if first_word == surname:
                                    match_score += 1000
        
        # --- 如果第一作者不匹配，檢查第二作者 ---
        if not is_author_match and author_count >= 2:
            if isinstance(authors, list) and len(authors) >= 2:
                second_author = authors[1]
                second_author_norm = _normalize_author_name(second_author)
                
                # 檢查第二作者標準化名稱是否在原始文本中
                if second_author_norm and second_author_norm in raw_text_lower:
                    is_author_match = True
                    match_score = len(second_author_norm)
                else:
                    # 檢查第二作者的名字部分或姓氏
                    if any('\u4e00' <= char <= '\u9fff' for char in second_author):
                        # 中文：先檢查名字部分（去掉姓氏，適用於 "志富" vs "鄭志富"）
                        if len(second_author) >= 2:
                            given_name = second_author[1:]  # "鄭志富" → "志富"
                            if given_name and given_name in raw_text_lower:
                                is_author_match = True
                                match_score = len(given_name)
                        
                        # 如果還是不匹配，檢查姓氏
                        if not is_author_match:
                            surname = second_author[0] if second_author else ''
                            if surname and surname in raw_text_lower:
                                is_author_match = True
                                match_score = len(surname)
                    else:
                        # 英文姓名：取姓氏
                        parts = second_author.split(',')
                        if len(parts) >= 1:
                            surname = parts[0].strip().lower()
                        else:
                            words = second_author.split()
                            surname = words[-1].lower() if words else ''
                        
                        # 檢查姓氏是否出現在原始引用文本中
                        if surname and surname in raw_text_lower:
                            surname_escaped = re.escape(surname)
                            surname_pattern = r'(?<![A-Za-z])' + surname_escaped + r'(?![A-Za-z])'
                            if re.search(surname_pattern, raw_text_lower, re.IGNORECASE):
                                is_author_match = True
                                match_score = len(surname)
        
        # --- 如果第一、二作者都不匹配，且是三作者格式，檢查第三作者 ---
        if not is_author_match and author_count >= 3:
            if isinstance(authors, list) and len(authors) >= 3:
                third_author = authors[2]
                third_author_norm = _normalize_author_name(third_author)
                
                # 檢查第三作者標準化名稱是否在原始文本中
                if third_author_norm and third_author_norm in raw_text_lower:
                    is_author_match = True
                    match_score = len(third_author_norm)
                else:
                    # 檢查第三作者的名字部分或姓氏
                    if any('\u4e00' <= char <= '\u9fff' for char in third_author):
                        # 中文：先檢查名字部分
                        if len(third_author) >= 2:
                            given_name = third_author[1:]
                            if given_name and given_name in raw_text_lower:
                                is_author_match = True
                                match_score = len(given_name)
                        
                        # 如果還是不匹配，檢查姓氏
                        if not is_author_match:
                            surname = third_author[0] if third_author else ''
                            if surname and surname in raw_text_lower:
                                is_author_match = True
                                match_score = len(surname)
                    else:
                        # 英文姓名：取姓氏
                        parts = third_author.split(',')
                        if len(parts) >= 1:
                            surname = parts[0].strip().lower()
                        else:
                            words = third_author.split()
                            surname = words[-1].lower() if words else ''
                        
                        # 檢查姓氏是否出現在原始引用文本中
                        if surname and surname in raw_text_lower:
                            surname_pattern = r'\b' + re.escape(surname) + r'\b'
                            if re.search(surname_pattern, raw_text_lower, re.IGNORECASE):
                                is_author_match = True
                                match_score = len(surname)

        # 如果作者完全不匹配，跳過這個 reference
        if not is_author_match:
            continue

        # --- 如果是雙作者，檢查兩個作者是否都匹配（加分） ---
        if citation_type == 'two_authors' and isinstance(authors, list) and len(authors) >= 2:
            first_author_norm = _normalize_author_name(authors[0])
            second_author_norm = _normalize_author_name(authors[1])
            
            if first_author_norm and second_author_norm:
                if first_author_norm in raw_text_lower and second_author_norm in raw_text_lower:
                    match_score = len(first_author_norm) + len(second_author_norm)
        
        # --- 如果是三作者，檢查三個作者是否都匹配（加分） ---
        if citation_type == 'three_authors' and isinstance(authors, list) and len(authors) >= 3:
            first_author_norm = _normalize_author_name(authors[0])
            second_author_norm = _normalize_author_name(authors[1])
            third_author_norm = _normalize_author_name(authors[2])
            
            if first_author_norm and second_author_norm and third_author_norm:
                if (first_author_norm in raw_text_lower and 
                    second_author_norm in raw_text_lower and 
                    third_author_norm in raw_text_lower):
                    match_score = len(first_author_norm) + len(second_author_norm) + len(third_author_norm)

        if match_score > best_match_score:
            best_match_score = match_score
            # 從 reference 的 authors 列表中提取第一作者姓氏
            ref_authors = reference_list[ref_idx].get('authors') or reference_list[ref_idx].get('author')
            if isinstance(ref_authors, list) and ref_authors:
                # 提取第一作者並只保留姓氏
                first_author_clean = str(ref_authors[0])
                first_author_clean = re.sub(r',.*$', '', first_author_clean).strip()
            else:
                first_author_clean = first_author

            best_match = {
                'author': first_author_clean,
                'year': ref.get('year'),
                'index': ref_idx
            }
    
    return best_match

def _detect_citation_author_type(raw_text_lower):
    """
    偵測內文引用的作者數量類型
    
    Args:
        raw_text_lower: 小寫的原始引用文本
    
    Returns:
        'et_al': 3+ 位作者（包含 et al.）
        'three_authors': 3 位作者（包含兩個頓號 、）
        'two_authors': 2 位作者（包含 & 或 and）
        'single_author': 1 位作者
        'organization': 機構名稱
    """
    # 檢查是否有 "et al."
    if re.search(r'et\s*al\.?|等人|等', raw_text_lower):
        return 'et_al'
    
    # 檢查是否有兩個頓號（三作者格式）
    # 例如：「作者一、作者二、作者三」
    if raw_text_lower.count('、') >= 2:
        return 'three_authors'
    
    # 檢查是否有 "&" 或 "and" 或中文連接詞
    if re.search(r'\s+&\s+|\s+and\s+|與|、', raw_text_lower):
        return 'two_authors'
    
    # 檢查是否是機構名稱（通常包含 Institute, Department, Center, Association 等關鍵字）
    org_keywords = [
        'institute', 'department', 'center', 'centre', 'association', 
        'organization', 'organisation', 'society', 'foundation', 
        'committee', 'council', 'agency', 'bureau', 'ministry',
        '研究所', '學會', '協會', '基金會', '委員會', '部門', '中心'
    ]
    if any(keyword in raw_text_lower for keyword in org_keywords):
        return 'organization'
    
    # 預設為單一作者
    return 'single_author'