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
        for junk in ['et al.', 'et al', 'and', '&', ',']:
            name = name.replace(junk, ' ')
        # 3. 只取第一個單字 (通常就是姓氏)
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

    # --- 1. 建立參考文獻的編號查找表 (針對 IEEE 格式加速查找) ---
    ref_map_by_id = {}
    for i, ref in enumerate(reference_list):
        if ref.get('ref_number'):
            ref_num = str(ref['ref_number']).strip()
            ref_map_by_id[ref_num] = i

    # --- 2. 遍歷內文引用 ---
    for cit in in_text_citations:
        is_found = False
        potential_year_error_hint = None # 用來記錄疑似正確的年份
        
        # 路徑 A: IEEE 格式引用 (優先用編號查，最準)
        if cit.get('ref_number'):
            cit_num = str(cit['ref_number']).strip()
            if cit_num in ref_map_by_id:
                is_found = True
                matched_indices.add(ref_map_by_id[cit_num])
        
        # 路徑 B: APA 格式引用 (用 "核心姓氏 + 年份" 掃描原始文字)
        if not is_found and cit.get('author') and cit.get('year'):
            # 準備特徵值
            cit_year = ''.join(filter(str.isdigit, str(cit['year']))) # 例如 "2022"
            cit_auth_core = get_core_author_name(cit['author'])       # 例如 "yuanjiang"
            
            # 只有當提取出有效的作者和年份時才進行比對
            if cit_year and cit_auth_core:
                for i, ref in enumerate(reference_list):
                    # 獲取參考文獻的原始文字 (包含所有資訊)
                    ref_original = str(ref.get('original', '')).lower()
                    ref_original_clean = clean_ref_text(ref_original)
                    
                    # 步驟 1: 檢查「核心姓氏」是否出現在參考文獻中
                    if cit_auth_core in ref_original_clean:
                        # 步驟 2: 如果作者對了，再檢查「年份」是否也存在
                        if cit_year in ref_original:
                            is_found = True
                            matched_indices.add(i)
                            break # 完美匹配，跳出迴圈
                        else:
                            # 作者對了但年份不對 -> 可能是年份引用錯誤
                            # 嘗試從該條參考文獻中抓一個 4 碼年份作為提示
                            # 這裡簡單抓取 19xx 或 20xx 的數字
                            years_in_ref = re.findall(r'(19\d{2}|20\d{2})', ref_original)
                            # 如果有抓到年份，且還沒記錄過提示，就記錄下來
                            if years_in_ref and not potential_year_error_hint:
                                potential_year_error_hint = years_in_ref[0]
        
        if not is_found:
            # 標記錯誤類型，方便前端 UI 顯示不同提示
            if potential_year_error_hint:
                cit['error_type'] = 'year_mismatch'
                cit['year_hint'] = potential_year_error_hint
            else:
                cit['error_type'] = 'missing'
            
            missing_in_refs.append(cit)

    # --- 3. 找出未使用的參考文獻 ---
    unused_refs = []
    for i, ref in enumerate(reference_list):
        if i not in matched_indices:
            unused_refs.append(ref)
            
    return missing_in_refs, unused_refs