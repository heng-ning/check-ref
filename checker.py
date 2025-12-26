import re
# ===== 交叉比對 =====
def check_references(in_text_citations, reference_list):
    """
    完整修正版比對函式：
    1. 解決 "et al." 等綴詞導致比對失敗的問題 (只比對姓氏核心)。
    2. 繞過解析器可能錯誤的 'year'/'author' 欄位，直接比對 'original' 原始文字。
    3. 加入「疑似年份錯誤」偵測，當作者對但年份不對時，標記提示。
    """
    
    # --- 輔助函式：提取作者核心姓氏 (去除 et al., and, & 等雜訊) ---
    def get_core_author_name(name):
        if not name: return ""
        # 1. 轉小寫
        name = str(name).lower()
        # 2. 移除常見綴詞，避免干擾
        for junk in ['et al.', 'et al', 'and', '&', ',','與', '和', '及']:
            name = name.replace(junk, ' ')
        # 3. 只取第一個單字 (通常就是姓氏)
        if any('\u4e00' <= char <= '\u9fff' for char in name):
            # 如果是中文，直接移除所有空白，回傳全名（例如 "張三"）
            return "".join(filter(str.isalnum, name))
        else:
            parts = name.split()
            if parts:
                # 只保留英數字，移除點號等
                return "".join(filter(str.isalnum, parts[0]))
            return ""

    # --- 輔助函式：清理參考文獻文字 ---
    def clean_ref_text(text):
        # 轉小寫，只保留英數字，用於高容錯比對
        return "".join(filter(str.isalnum, str(text).lower()))

    matched_indices = set()
    missing_in_refs = []
    year_mismatch_map = {}  # 記錄疑似年份錯誤 {ref_index: [引用列表]}

    # --- 1. 建立參考文獻的編號查找表 ---
    ref_map_by_id = {}
    for i, ref in enumerate(reference_list):
        if ref.get('ref_number'):
            ref_num = str(ref['ref_number']).strip()
            ref_map_by_id[ref_num] = i

    # --- 2. 遍歷內文引用 ---
    for cit in in_text_citations:
        is_found = False
        potential_ref_index = None  # 記錄疑似對應的參考文獻索引
        
        # 路徑 A: IEEE 格式引用
        if cit.get('ref_number'):
            cit_num = str(cit['ref_number']).strip()
            if cit_num in ref_map_by_id:
                is_found = True
                matched_indices.add(ref_map_by_id[cit_num])
        
        # 路徑 B: APA 格式引用
        if not is_found and cit.get('author') and cit.get('year'):
            cit_year = ''.join(filter(str.isdigit, str(cit['year'])))
            cit_auth_core = get_core_author_name(cit['author'])
            
            if cit_year and cit_auth_core:
                found_for_this_citation = False
                
                for i, ref in enumerate(reference_list):
                    ref_original = str(ref.get('original', '')).lower()
                    ref_original_clean = clean_ref_text(ref_original)
                    
                    # 步驟 1: 檢查作者
                    if cit_auth_core in ref_original_clean:
                        # 步驟 2: 檢查年份
                        if cit_year in ref_original:
                            is_found = True
                            found_for_this_citation = True
                            matched_indices.add(i)
                        else:
                            # 作者對但年份錯：記錄到 year_mismatch_map
                            if not found_for_this_citation:
                                potential_ref_index = i
                                years_in_ref = re.findall(r'(19\d{2}|20\d{2})', ref_original)
                                
                                if years_in_ref:
                                    if i not in year_mismatch_map:
                                        year_mismatch_map[i] = []
                                    
                                    year_mismatch_map[i].append({
                                        'citation': cit.get('original'),
                                        'cited_year': cit_year,
                                        'correct_year': years_in_ref[0]
                                    })
        
        # 只有「完全找不到」才算遺漏
        if not is_found and potential_ref_index is None:
            cit['error_type'] = 'missing'
            missing_in_refs.append(cit)

    # --- 3. 找出未使用的參考文獻，並標註疑似年份錯誤 ---
    unused_refs = []
    year_error_refs = []  # 存放年份錯誤的文獻

    for i, ref in enumerate(reference_list):
        if i not in matched_indices:
            ref_info = ref.copy()
            
            # 檢查是否有年份錯誤紀錄
            if i in year_mismatch_map:
                ref_info['year_mismatch'] = year_mismatch_map[i]
                year_error_refs.append(ref_info)
            else:
                unused_refs.append(ref_info)

    return missing_in_refs, unused_refs, year_error_refs
