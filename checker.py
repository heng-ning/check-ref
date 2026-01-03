import re

# ===== 交叉比對 =====

def check_references(in_text_citations, reference_list):
    """
    完整修正版比對函式：
    1. [New] 支援 IEEE 多重引用比對 ([6,7,8])，不會漏掉後面的號碼。
    2. 解決 "et al." 綴詞問題。
    3. 繞過解析錯誤直接比對 raw text。
    4. 加入年份錯誤偵測。
    """
    # --- 輔助函式：提取作者核心姓氏 ---
    def get_core_author_name(name):
        if not name: return ""
        name = str(name).lower()
        for junk in ['et al.', 'et al', 'and', '&', ',','與', '和', '及','等人', '等']:
            name = name.replace(junk, ' ')
        
        if any('\u4e00' <= char <= '\u9fff' for char in name):
            return "".join(filter(str.isalnum, name))
        else:
            parts = name.split()
            if parts:
                return "".join(filter(str.isalnum, parts[0]))
            return ""

    # --- 輔助函式：清理參考文獻文字 ---
    def clean_ref_text(text):
        return "".join(filter(str.isalnum, str(text).lower()))

    matched_indices = set()
    missing_in_refs = []
    year_mismatch_map = {} 

    # --- 1. 建立參考文獻的編號查找表 ---
    ref_map_by_id = {} 
    for i, ref in enumerate(reference_list):
        if ref.get('ref_number'):
            ref_num = str(ref['ref_number']).strip().strip('.')
            ref_map_by_id[ref_num] = i
    # --- 2. 遍歷內文引用 ---
    for cit in in_text_citations:
        is_found = False
        potential_ref_index = None 
        
        # 路徑 A: IEEE 格式引用 (修正版)
        if cit.get('ref_number'):
            # 優先檢查是否有 all_numbers (新欄位)，如果沒有則檢查 ref_number (舊相容)
            numbers_to_check = cit.get('all_numbers', [str(cit['ref_number'])])
            any_matched = False
            for num in numbers_to_check:
                num_str = str(num).strip()
                if num_str in ref_map_by_id:
                    matched_indices.add(ref_map_by_id[num_str]) # 標記該編號為「已使用」
                    any_matched = True
            if any_matched:
                is_found = True
        
        # 路徑 B: APA 格式引用
        if not is_found and cit.get('author') and cit.get('year'):
            cit_year = ''.join(filter(str.isdigit, str(cit['year'])))
            cit_auth_core = get_core_author_name(cit['author'])
            
            if cit_year and cit_auth_core:
                found_for_this_citation = False
                
                for i, ref in enumerate(reference_list):
                    ref_original = str(ref.get('original', '')).lower()
                    ref_original_clean = clean_ref_text(ref_original)
                    
                    if cit_auth_core in ref_original_clean:
                        if cit_year in ref_original:
                            is_found = True
                            found_for_this_citation = True
                            matched_indices.add(i)
                        else:
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
        
        if not is_found and potential_ref_index is None:
            cit['error_type'] = 'missing'
            missing_in_refs.append(cit)

    # --- 3. 找出未使用的參考文獻 ---
    unused_refs = []
    year_error_refs = [] 

    for i, ref in enumerate(reference_list):
        if i not in matched_indices:
            ref_info = ref.copy()
            if i in year_mismatch_map:
                ref_info['year_mismatch'] = year_mismatch_map[i]
                year_error_refs.append(ref_info)
            else:
                unused_refs.append(ref_info)

    return missing_in_refs, unused_refs, year_error_refs
