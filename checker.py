import re

# ===== 交叉比對 =====
def check_references(in_text_citations, reference_list):
    """
    直接使用已解析並存入 JSON 的參考文獻資料
    
    改進重點：
    1. 不再重複解析作者姓名，直接使用 reference_list 中的 'author' 或 'authors' 欄位
    2. 不再重複解析年份，直接使用 reference_list 中的 'year' 欄位
    3. 統一使用標準化的作者姓名比對邏輯
    4. 支援 IEEE 多重引用比對 ([6,7,8])
    5. 改進年份錯誤偵測
    
    Args:
        in_text_citations: 內文引用列表（包含 format, author, year, ref_number 等）
        reference_list: 參考文獻列表（已解析的 JSON 資料）
    
    Returns:
        missing_in_refs: 遺漏的參考文獻列表
        unused_refs: 未使用的參考文獻列表
        year_error_refs: 年份錯誤的參考文獻列表
    """
    
    # --- 從內文引用原始文本提取第一作者 ---
    def extract_first_author_from_citation(cit):
        """
        從內文引用的原始文本中提取第一作者
        
        處理多種格式：
        - 1 位作者: (Smith, 2020) 或 Smith (2020)
        - 2 位作者: (Smith & Jones, 2020) 或 Smith and Jones (2020)
        - 3 位以上: (Smith et al., 2020) 或 Smith et al. (2020)
        
        Args:
            cit: 內文引用字典（包含 original, author 等欄位）
        
        Returns:
            第一作者的姓名字串，如果無法提取則返回 None
        """
        # 優先使用已解析的 author 欄位（如果存在且是單一作者）
        if cit.get('author'):
            author_str = str(cit['author'])
            # 清理多余空格（处理 "Pak     et al." 这种情况）
            author_str = re.sub(r'\s+', ' ', author_str).strip()
            
            # 如果 author 欄位中不包含連接詞（&, and, 與, 和, et al.），則直接使用
            if not re.search(r'\s+&\s+|\s+and\s+|、|與|et\s+al\.?|等人', author_str, re.IGNORECASE):
                return author_str
            
            # 如果包含 et al.，從 author 字段提取第一作者（不需要回退到原始文本）
            if re.search(r'et\s+al\.?|等人|等', author_str, re.IGNORECASE):
                author_cleaned = re.sub(r'\s+et\s+al\.?.*$', '', author_str, flags=re.IGNORECASE)
                author_cleaned = re.sub(r'等人.*$', '', author_cleaned)  # 移除空格要求
                author_cleaned = re.sub(r'\s*等(?![^\u4e00-\u9fff]).*$', '', author_cleaned)
                author_cleaned = author_cleaned.strip()
                # 清理多余空格并提取第一作者（处理可能的顿号分隔的多作者情况）
                author_cleaned = re.sub(r'\s+', ' ', author_cleaned).strip()
                first_author = re.split(r'\s+&\s+|\s+and\s+|、|與', author_cleaned)[0].strip()
                return re.sub(r'\s+', ' ', first_author).strip()
            
            # 如果包含雙作者連接詞，提取第一個作者
            if re.search(r'\s+&\s+|\s+and\s+|、|與', author_str):
                first_author = re.split(r'\s+&\s+|\s+and\s+|、|與', author_str)[0].strip()
                return re.sub(r'\s+', ' ', first_author).strip()
        
        # 否則從原始文本中提取
        original_text = cit.get('original', '')
        if not original_text:
            return None
        
        # 先清理原始文本中的多余空格（处理 "Pak  et al." 这种情况）
        original_text = re.sub(r'\s+', ' ', original_text)
        
        # 處理多引用情況：如果包含分號，提取第一個引用部分
        # 例如："(Smith et al., 2020; Andy et al., 2021; Bob et al., 2022)" → "(Smith et al., 2020)"
        if re.search(r'[;；]', original_text):
            # 找到第一個分號的位置
            semicolon_match = re.search(r'[;；]', original_text)
            if semicolon_match:
                # 提取第一個分號之前的所有內容
                first_part = original_text[:semicolon_match.start()].strip()
                # 確保以左括號開頭（如果沒有，添加）
                if not first_part.startswith(('(', '（')):
                    first_part = '(' + first_part
                # 確保以右括號結尾：找到第一個年份後添加右括號
                year_match = re.search(r'\d{4}[a-z]?', first_part)
                if year_match:
                    # 提取到年份結束位置，然後添加右括號
                    end_pos = year_match.end()
                    # 移除年份之後可能存在的右括號或分號
                    first_part_clean = first_part[:end_pos].rstrip(')）;；,，')
                    original_text = first_part_clean + ')'
                else:
                    # 如果沒找到年份，保持原樣
                    original_text = first_part
        
        # 處理括號式: (作者, 年份) 或 (作者 & 作者, 年份) 或 (作者 et al., 年份)
        paren_match = re.search(
            r'[（(]\s*([\w\s\u4e00-\u9fff\-\.]+?)(?:\s*(?:&|and|與|、)\s*[\w\s\u4e00-\u9fff\-\.]+?)*(?:\s*,?\s*et\s*al\.?)?\s*[,，]\s*\d{4}',
            original_text,
            re.IGNORECASE | re.UNICODE
        )
        if paren_match:
            author_part = paren_match.group(1).strip()
            # 清理多余空格
            author_part = re.sub(r'\s+', ' ', author_part).strip()
            
            # 移除逗號及其後的內容（例如 "Hundhausen, C. D." → "Hundhausen"）
            author_part = re.sub(r',.*$', '', author_part).strip()
            
            # 如果包含 et al.，先移除 et al. 部分
            if re.search(r'et\s+al\.?|等人|等', author_part, re.IGNORECASE):
                author_part = re.sub(r'\s+et\s+al\.?.*$', '', author_part, flags=re.IGNORECASE)
                author_part = re.sub(r'\s*等人.*$', '', author_part)
                author_part = re.sub(r'\s*等(?![^\u4e00-\u9fff]).*$', '', author_part)  # 只匹配「等」後面不是中文的情況
                author_part = author_part.strip()
            
            # 提取第一個作者（去除可能的連接詞：&, and, 與, 和）
            first_author = re.split(r'\s+&\s+|\s+and\s+|、|與', author_part)[0].strip()
            # 再次清理多余空格
            first_author = re.sub(r'\s+', ' ', first_author).strip()
            return first_author
        
        # 處理敘述式: 作者 (年份) 或 作者 & 作者 (年份) 或 作者 et al. (年份)
        # 找到括號前的文本部分，提取作者名
        # 匹配模式：任意文本 + 作者部分 + (年份)
        narrative_match = re.search(
            r'([\w\u4e00-\u9fff][^（(]*?)\s*[（(]\s*\d{4}',
            original_text,
            re.IGNORECASE | re.UNICODE
        )
        if narrative_match:
            # 獲取括號前的文本，然後提取最後的作者部分
            text_before_paren = narrative_match.group(1).strip()
            # 清理多余空格
            text_before_paren = re.sub(r'\s+', ' ', text_before_paren).strip()
            
            # 如果包含 et al.，提取 et al. 前的部分
            if re.search(r'et\s+al\.?|等人|等', text_before_paren, re.IGNORECASE):
                # 移除 et al. 及之後的內容（注意：et 和 al 之間可能有多余空格）
                author_part = re.sub(r'\s+et\s+al\.?.*$', '', text_before_paren, flags=re.IGNORECASE)
                author_part = re.sub(r'\s*等人.*$', '', author_part)
                author_part = re.sub(r'\s*等(?![^\u4e00-\u9fff]).*$', '', author_part)  # 只匹配「等」後面不是中文的情況
            else:
                author_part = text_before_paren
            
            # 清理多余空格
            author_part = re.sub(r'\s+', ' ', author_part).strip()
            
            # 如果包含雙作者連接詞，提取第一個作者
            if re.search(r'\s+&\s+|\s+and\s+|、|與', author_part):
                first_author = re.split(r'\s+&\s+|\s+and\s+|、|與', author_part)[0].strip()
                # 清理多余空格
                first_author = re.sub(r'\s+', ' ', first_author).strip()
                return first_author
            
            # 單一作者：取最後的單詞或詞組（因為前面可能有其他文本）
            # 例如："根據Smith (2020)" → 提取 "Smith"
            # 例如："Smith (2020)" → 提取 "Smith"
            words = re.findall(r'[\w\u4e00-\u9fff]+', author_part)
            if words:
                # 如果是中文，可能有多個字組成姓名；如果是英文，取最後一個單詞（通常是姓氏）
                if any('\u4e00' <= char <= '\u9fff' for char in author_part):
                    # 中文：取最後的1-4個字（通常是姓名）
                    chinese_chars = re.findall(r'[\u4e00-\u9fff]+', author_part)
                    if chinese_chars:
                        result = chinese_chars[-1]  # 取最後的中文詞組
                        # 清理多余空格
                        return re.sub(r'\s+', ' ', result).strip()
                else:
                    # 英文：取最後一個單詞（通常是姓氏）
                    result = words[-1] if words else author_part
                    # 清理多余空格
                    return re.sub(r'\s+', ' ', result).strip()
            
            # 清理多余空格
            return re.sub(r'\s+', ' ', author_part).strip()
        
        # 如果都無法匹配，返回 None
        return None
    
    # --- 標準化作者姓名以便比對 ---
    def normalize_author(author_data):
        """
        將作者資料標準化為可比對的格式
        
        Args:
            author_data: 可能是字串、列表或 None
        
        Returns:
            標準化後的作者姓名（小寫、去除特殊符號）
        """
        if not author_data:
            return ""
        
        # 如果是列表，取第一作者
        if isinstance(author_data, list):
            if not author_data:
                return ""
            author_str = str(author_data[0])
            # 只保留姓氏部分（移除逗號及其後的內容，例如 "Hundhausen, C. D." → "Hundhausen"）
            author_str = re.sub(r',.*$', '', author_str).strip()
        else:
            author_str = str(author_data)
        
        # 先清理多余空格（处理 "Pak  et al." 这种情况）
        author_str = re.sub(r'\s+', ' ', author_str).strip()
        
        # 轉小寫
        author_str = author_str.lower()
        
        # 移除常見的綴詞和連接詞
        for junk in ['et al.', 'et al', 'and', '&', ',', '與', '和', '及', '等人', '等', '.', '、']:
            author_str = author_str.replace(junk, ' ')
        
        # 再次清理多余空格（因为替换后可能产生多余空格）
        author_str = re.sub(r'\s+', ' ', author_str).strip()
        
        # 提取核心姓名部分
        # 中文：保留所有漢字和字母數字
        # 英文：取第一個單詞（通常是姓氏）
        if any('\u4e00' <= char <= '\u9fff' for char in author_str):
            # 中文作者：保留所有字母數字字元
            core = "".join(filter(lambda c: c.isalnum() or '\u4e00' <= c <= '\u9fff', author_str))
        else:
            # 英文作者：取第一個單詞
            parts = author_str.split()
            if parts:
                core = "".join(filter(str.isalnum, parts[0]))
            else:
                core = ""
        
        return core.strip()
    
    # --- 標準化年份 ---
    def normalize_year(year_data):
        """
        提取並標準化年份
        
        Args:
            year_data: 年份資料（可能是字串或數字）
        
        Returns:
            標準化後的年份字串（4位數字）
        """
        if not year_data:
            return ""
        
        year_str = str(year_data)
        # 提取4位數年份
        digits = ''.join(filter(str.isdigit, year_str))
        
        # 尋找19xx或20xx格式的年份
        year_match = re.search(r'(19\d{2}|20\d{2})', digits)
        if year_match:
            return year_match.group(1)
        
        return digits[:4] if len(digits) >= 4 else digits
    
    # --- 初始化 ---
    matched_indices = set()  # 記錄已比對到的參考文獻索引
    missing_in_refs = []     # 內文有引用但參考文獻缺漏
    missing_in_refs_set = set()  # 用於去重：記錄已添加的遺漏引用標識符
    year_mismatch_map = {}   # 作者匹配但年份不符
    
    # --- 1. 建立參考文獻快速查找表 ---
    
    # IEEE 格式：以編號為 key
    ref_map_by_number = {}
    # APA 格式：以 (作者, 年份) 為 key
    ref_map_by_author_year = {}
    # 作者索引：以作者為 key，存放所有相關的參考文獻索引
    ref_map_by_author = {}
    
    for i, ref in enumerate(reference_list):
        # 建立編號索引（IEEE）
        if ref.get('ref_number'):
            ref_num = str(ref['ref_number']).strip().strip('.')
            ref_map_by_number[ref_num] = i
        
        # 建立作者-年份索引（APA）
        ref_authors = ref.get('authors') or ref.get('author')
        ref_year = normalize_year(ref.get('year'))
        
        # 【修改】同時建立「完整作者」和「第一作者」的索引
        # 完整作者索引（用於精確匹配）
        ref_author_full = normalize_author(ref_authors)
        if ref_author_full and ref_year:
            key = (ref_author_full, ref_year)
            ref_map_by_author_year[key] = i
        
        # 【新增】第一作者索引（用於「等人」匹配）
        if isinstance(ref_authors, list) and ref_authors:
            first_author_raw = ref_authors[0]
            
            # 【修正】如果第一個元素包含頓號，表示作者被打包在一個字串裡，需要拆分
            if isinstance(first_author_raw, str) and '、' in first_author_raw:
                # 拆分作者字串，取第一個作者
                first_author_raw = first_author_raw.split('、')[0].strip()
            
            ref_first_author = normalize_author(first_author_raw)
        else:
            # 字串格式，可能也包含多個作者
            if isinstance(ref_authors, str) and '、' in ref_authors:
                first_author_raw = ref_authors.split('、')[0].strip()
                ref_first_author = normalize_author(first_author_raw)
            else:
                ref_first_author = normalize_author(ref_authors)

        if ref_first_author and ref_year:
            key_first = (ref_first_author, ref_year)
            # 如果這個 key 還沒有被佔用，才加入（避免覆蓋完整作者索引）
            if key_first not in ref_map_by_author_year:
                ref_map_by_author_year[key_first] = i
        
        # 建立作者索引（用於年份錯誤檢測）
        if ref_author_full:
            if ref_author_full not in ref_map_by_author:
                ref_map_by_author[ref_author_full] = []
            ref_map_by_author[ref_author_full].append({
                'index': i,
                'year': ref_year,
                'original': ref.get('original', '')
            })
    
    # --- 2. 遍歷內文引用，進行比對 ---
    for cit in in_text_citations:
        is_found = False
        potential_year_mismatch_index = None
        
        # 預先提取和標準化作者、年份信息（用於去重和比對）
        cit_author = None
        cit_year = None
        
        # 路徑 A: IEEE 格式引用（使用編號比對）
        if cit.get('format') == 'IEEE' or cit.get('ref_number'):
            # 檢查 all_numbers（多重引用）或 ref_number（單一引用）
            numbers_to_check = cit.get('all_numbers', [])
            if not numbers_to_check and cit.get('ref_number'):
                numbers_to_check = [str(cit['ref_number'])]
            
            any_matched = False
            for num in numbers_to_check:
                num_str = str(num).strip()
                if num_str in ref_map_by_number:
                    ref_index = ref_map_by_number[num_str]
                    matched_indices.add(ref_index)
                    any_matched = True
            
            if any_matched:
                is_found = True
        
        # 路徑 B: APA 格式引用（使用作者-年份比對）
        if not is_found and cit.get('format') == 'APA':
            # 改進：先從內文引用原始文本提取第一作者（處理多作者情況）
            first_author_str = extract_first_author_from_citation(cit)
            if not first_author_str:
                # 如果無法從原始文本提取，回退到使用 author 欄位
                first_author_str = cit.get('author')
            
            cit_author = normalize_author(first_author_str)
            cit_year = normalize_year(cit.get('year'))
            
            if cit_author and cit_year:
                # 【新增】檢查內文引用是否包含「等人」
                is_et_al_citation = False
                cit_original = cit.get('original', '')
                if re.search(r'等人|等|et\s+al\.?', cit_original, re.IGNORECASE):
                    is_et_al_citation = True
                
                # 【新增】如果是「等人」格式，只用第一作者 + 年份比對所有參考文獻
                if is_et_al_citation:
                    # 遍歷所有參考文獻，找到第一作者 + 年份匹配的
                    for ref_idx, ref in enumerate(reference_list):
                        ref_authors = ref.get('authors') or ref.get('author')
                        ref_year = normalize_year(ref.get('year'))
                        
                        # 提取參考文獻的第一作者
                        if isinstance(ref_authors, list) and ref_authors:
                            ref_first_author = normalize_author(ref_authors[0])
                        else:
                            ref_first_author = normalize_author(ref_authors)
                        
                        # 比對：第一作者相同 + 年份相同
                        if ref_first_author == cit_author and ref_year == cit_year:
                            matched_indices.add(ref_idx)
                            is_found = True
                            break
                
                # 如果不是「等人」格式，或者「等人」格式沒找到匹配，則繼續原有的精確匹配邏輯
                if not is_found:
                    # 精確匹配：作者 + 年份
                    key = (cit_author, cit_year)
                    if key in ref_map_by_author_year:
                        ref_index = ref_map_by_author_year[key]
                        
                        matched_indices.add(ref_index)
                        is_found = True
                    
                    # 如果沒有精確匹配，檢查是否有作者匹配但年份不同的情況
                    if not is_found and cit_author in ref_map_by_author:
                        for ref_info in ref_map_by_author[cit_author]:
                            if ref_info['year'] != cit_year:
                                # 發現年份不符
                                potential_year_mismatch_index = ref_info['index']
                                
                                if potential_year_mismatch_index not in year_mismatch_map:
                                    year_mismatch_map[potential_year_mismatch_index] = []
                                
                                year_mismatch_map[potential_year_mismatch_index].append({
                                    'citation': cit.get('original', ''),
                                    'cited_year': cit_year,
                                    'correct_year': ref_info['year']
                                })
        
        # 如果完全找不到匹配，標記為遺漏
        if not is_found and potential_year_mismatch_index is None:
            # 生成唯一標識符用於去重
            cit_format = cit.get('format', '')
            
            if cit_format == 'APA':
                # APA 格式：只使用標準化的作者和年份（不依賴原始文本，避免因空格等差異導致重複）
                if cit_author is None:
                    first_author_str = extract_first_author_from_citation(cit)
                    if not first_author_str:
                        first_author_str = cit.get('author')
                    cit_author = normalize_author(first_author_str)
                
                if cit_year is None:
                    cit_year = normalize_year(cit.get('year'))
                
                # 只使用標準化的作者和年份生成唯一鍵
                if cit_author and cit_year:
                    unique_key = f"{cit_format}::{cit_author}::{cit_year}"
                else:
                    # 如果無法提取作者或年份，使用原始文本（清理後）
                    cit_original_normalized = re.sub(r'\s+', ' ', str(cit.get('original', '')).strip()).lower()
                    unique_key = f"{cit_format}::{cit_original_normalized}"
            else:
                # IEEE 格式：使用編號作為唯一標識（編號是最可靠的標識）
                cit_ref_number = cit.get('ref_number', '')
                cit_all_numbers = cit.get('all_numbers', [])
                if cit_all_numbers:
                    # 對編號進行排序，確保 [6,7,8] 和 [8,7,6] 被視為相同
                    numbers_str = ','.join(sorted([str(n).strip() for n in cit_all_numbers]))
                    unique_key = f"{cit_format}::{numbers_str}"
                elif cit_ref_number:
                    unique_key = f"{cit_format}::{str(cit_ref_number).strip()}"
                else:
                    # 如果沒有編號，使用原始文本（清理後）
                    cit_original_normalized = re.sub(r'\s+', ' ', str(cit.get('original', '')).strip()).lower()
                    unique_key = f"{cit_format}::{cit_original_normalized}"
            
            # 只有當這個引用尚未被記錄時才添加
            if unique_key not in missing_in_refs_set:
                missing_in_refs_set.add(unique_key)
                cit_copy = cit.copy()
                cit_copy['error_type'] = 'missing'
                missing_in_refs.append(cit_copy)
    
    # --- 3. 找出未使用的參考文獻 ---
    
    unused_refs = []
    year_error_refs = []
    
    for i, ref in enumerate(reference_list):
        if i not in matched_indices:
            ref_copy = ref.copy()
            
            # 如果這個未使用的文獻有年份錯誤記錄
            if i in year_mismatch_map:
                ref_copy['year_mismatch'] = year_mismatch_map[i]
                year_error_refs.append(ref_copy)
            else:
                # 純粹未使用
                unused_refs.append(ref_copy)
    
    return missing_in_refs, unused_refs, year_error_refs


def validate_references_integrity(reference_list):
    """
    驗證參考文獻列表的完整性
    
    檢查項目：
    1. 是否有重複的編號（IEEE）
    2. 是否有重複的作者-年份組合（APA）
    3. 是否有缺失的必要欄位
    
    Args:
        reference_list: 參考文獻列表
    
    Returns:
        dict: 包含驗證結果的字典
    """
    issues = {
        'duplicate_numbers': [],
        'duplicate_author_year': [],
        'missing_fields': [],
        'invalid_years': []
    }
    
    seen_numbers = {}
    seen_author_year = {}
    
    for i, ref in enumerate(reference_list):
        ref_num = i + 1
        
        # 檢查 IEEE 編號重複
        if ref.get('ref_number'):
            num = str(ref['ref_number'])
            if num in seen_numbers:
                issues['duplicate_numbers'].append({
                    'number': num,
                    'indices': [seen_numbers[num], ref_num]
                })
            else:
                seen_numbers[num] = ref_num
        
        # 檢查 APA 作者-年份重複
        author = ref.get('authors') or ref.get('author')
        year = ref.get('year')
        if author and year:
            key = (str(author), str(year))
            if key in seen_author_year:
                issues['duplicate_author_year'].append({
                    'author': author,
                    'year': year,
                    'indices': [seen_author_year[key], ref_num]
                })
            else:
                seen_author_year[key] = ref_num
        
        # 檢查必要欄位
        missing = []
        if not (ref.get('authors') or ref.get('author')):
            missing.append('author')
        if not ref.get('title'):
            missing.append('title')
        if not ref.get('year'):
            missing.append('year')
        
        if missing:
            issues['missing_fields'].append({
                'index': ref_num,
                'missing': missing,
                'original': ref.get('original', '')[:100]
            })
        
        # 檢查年份格式
        if ref.get('year'):
            year_str = str(ref['year'])
            if not re.search(r'(19\d{2}|20\d{2})', year_str):
                issues['invalid_years'].append({
                    'index': ref_num,
                    'year': year_str,
                    'original': ref.get('original', '')[:100]
                })
    
    return issues