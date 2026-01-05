import re
from utils.text_processor import (
    normalize_citation_for_matching,
    is_valid_year
)

def extract_in_text_citations(content_paragraphs):
    full_text = " ".join(content_paragraphs)
    citations = []
    citation_ids = set()
    
    # 先處理多引用格式，再處理單一引用
    
    # --- 1. 先處理 APA 多引用: (作者1, 年份1; 作者2, 年份2) ---
    pattern_apa_multi = re.compile(
        r'[（(]\s*([^)）]+?[;；][^)）]+?)\s*[）)]',  # ← 強制要求有分號
        re.UNICODE
    )
    for match in pattern_apa_multi.finditer(full_text):
        inner_text = match.group(1)
        segments = re.split(r'\s*[;；]\s*', inner_text)
        
        if len(segments) > 1:
            citation_id_check = f"{match.start()}-{match.end()}"
            if citation_id_check in citation_ids:
                continue
                
            for idx, seg in enumerate(segments):
                seg_match = re.match(
                    r'([\w\s\u4e00-\u9fff&,、\-\.]+?(?:\s+(?:et\s*al\.?|等人?|等))?)\s*[,，]\s*(\d{4}[a-z]?)',
                    seg.strip()
                )
                if seg_match:
                    author = seg_match.group(1).strip()
                    year = seg_match.group(2)[:4]
                    
                    if not author.isdigit() and is_valid_year(year):
                        citation_id = f"{match.start()}-multi-{idx}"
                        if citation_id not in citation_ids:
                            normalized = normalize_citation_for_matching(seg.strip())
                            citations.append({
                                'author': author,
                                'co_author': None,
                                'year': year,
                                'original': match.group(0),
                                'normalized': normalized,
                                'position': match.start(),
                                'type': 'APA-parenthetical-multi',
                                'format': 'APA'
                            })
                            citation_ids.add(citation_id)
            
            citation_ids.add(f"{match.start()}-{match.end()}")
    
    # --- 2. 再處理 APA 單一括號式: (作者, 年份) ---
    pattern_apa1 = re.compile(
        r'(?<![0-9])[（(]\s*([\w\s\u4e00-\u9fff\-\.]+?)\s*(?:(?:&|and|與|、)\s*([\w\s\u4e00-\u9fff\-\.]+?))?\s*'
        r'(?:,?\s*et\s*al\.?)?\s*[,，]\s*(\d{4}[a-z]?)\s*[）)]',
        re.UNICODE | re.IGNORECASE
    )
    for match in pattern_apa1.finditer(full_text):
        citation_id = f"{match.start()}-{match.end()}"
        if citation_id in citation_ids:  # ← 跳過已處理的
            continue
            
        author1 = match.group(1).strip()
        author2 = match.group(2).strip() if match.group(2) else None
        year = match.group(3)[:4]
        
        if author1.isdigit(): 
            continue
        
        if is_valid_year(year):
            normalized = normalize_citation_for_matching(match.group(0))
            citations.append({
                'author': author1,
                'co_author': author2,
                'year': year,
                'original': match.group(0),
                'normalized': normalized,
                'position': match.start(),
                'type': 'APA-parenthetical',
                'format': 'APA'
            })
            citation_ids.add(citation_id)

    # --- APA 敘述式: 作者 (年份) ---
    pattern_apa2 = re.compile(
        r'(?<![0-9])([\w\u4e00-\u9fff]+(?:\s+(?:et\s*al\.?|等人?|等))?)\s*[（(]\s*(\d{4}[a-z]?)\s*[）)]',
        re.UNICODE | re.IGNORECASE
    )
    for match in pattern_apa2.finditer(full_text):
        author = match.group(1).strip()
        year = match.group(2)[:4]
        
        # ========== [修正邏輯] 移除雜訊前綴 ==========
        junk_prefixes = [
            '本研究不僅再次驗證', '這些觀點皆與', '本研究採用', '此點亦與','等人則表示', 
            '而這與', '本研究', '也支持', '而在與', '這顯示',
            '根據', '依據', '參見', '參照', '此與', '亦與', '而這',
            '顯示', '指出', '發現', '認為', '以及', '至於', '反觀','結合',
            '如', '由', '採', '而', '與', '和', '及', '對', '故', 
            '經', '至', '則', '並', '但', '這'
        ]
        
        clean_author = author
        keep_cleaning = True
        while keep_cleaning:
            keep_cleaning = False
            for prefix in junk_prefixes:
                if clean_author.startswith(prefix):
                    if len(clean_author) > len(prefix):
                        clean_author = clean_author[len(prefix):].strip()
                        keep_cleaning = True 
                    break
        author = clean_author
        # ==========================================

        if author.isdigit(): continue
        
        if is_valid_year(year):
            citation_id = f"{match.start()}-{match.end()}"
            if citation_id not in citation_ids:
                normalized = normalize_citation_for_matching(match.group(0))
                citations.append({
                    'author': author,
                    'co_author': None,
                    'year': year,
                    'original': match.group(0),
                    'normalized': normalized,
                    'position': match.start(),
                    'type': 'APA-narrative',
                    'format': 'APA'
                })
                citation_ids.add(citation_id)
    
    # --- IEEE 數字式: [n] ---
    pattern_ieee_range_brackets = re.compile(
        r'([【\[]\s*\d+\s*[】\]])\s*[–\-\—~～]\s*([【\[]\s*\d+\s*[】\]])',
        re.UNICODE
    )
    for match in pattern_ieee_range_brackets.finditer(full_text):
        # 提取起點與終點，例如從 "[13]" 提取 13，從 "[16]" 提取 16
        start_bracket = match.group(1)
        end_bracket = match.group(2)
        
        start_n = int(re.search(r'\d+', start_bracket).group(0))
        end_n = int(re.search(r'\d+', end_bracket).group(0))
        # === [新增] 排除起點或終點為 0 的情況 ===
        if start_n == 0 or end_n == 0:
            continue

        extracted_numbers = []
        
        # 限制範圍大小 (防止誤判，例如 [2020]-[2021] 年份)
        if start_n < end_n and (end_n - start_n) < 100:
            for k in range(start_n, end_n + 1):
                extracted_numbers.append(str(k))
        
        # 過濾雜訊 (沿用您原本的過濾邏輯)
        final_numbers = []
        for num in extracted_numbers:
            val = int(num)
            if val == 0: continue
            if val > 2000: continue
            final_numbers.append(str(val))
            
        if not final_numbers: continue

        citation_id = f"{match.start()}-{match.end()}"
        if citation_id not in citation_ids:
            normalized = normalize_citation_for_matching(match.group(0))
            
            citations.append({
                'author': None,
                'co_author': None,
                'year': None,
                'ref_number': final_numbers[0], 
                'all_numbers': final_numbers,
                'original': match.group(0),
                'normalized': normalized,
                'position': match.start(),
                'type': 'IEEE-numeric-range', # 標記為特殊範圍格式
                'format': 'IEEE'
            })
            citation_ids.add(citation_id)
    pattern_ieee_robust = re.compile(
        r'[【\[]\s*(\d+(?:[–\-\—~～,;\s]+\d+)*)\s*[】\]]', 
        re.UNICODE
    )

    for match in pattern_ieee_robust.finditer(full_text):
        content_str = match.group(1)
        if re.match(r'^0\b', content_str):  # 開頭就是 0
            continue
        if re.search(r'[,;]\s*0\b', content_str):  # 中間有逗號+0（例如 "3, 0" 或 "1,0"）
            continue
        raw_parts = re.split(r'\s*[,;]\s*', content_str)
        temp_numbers = [] # 先暫存，等等要過濾
        
        for part in raw_parts:
            part = part.strip()
            # 處理範圍
            range_match = re.match(r'(\d+)\s*[–\-\—~～]\s*(\d+)', part)
            if range_match:
                start_n = int(range_match.group(1))
                end_n = int(range_match.group(2))
                # === [新增] 排除範圍含 0 的 (例如 [0-5]) ===
                if start_n == 0 or end_n == 0:
                    continue
                if start_n < end_n and (end_n - start_n) < 100:
                    for k in range(start_n, end_n + 1):
                        temp_numbers.append(str(k))
            elif part.isdigit():
                temp_numbers.append(part)
        
        # === [新增] 過濾雜訊 ===
        extracted_numbers = []
        for num in temp_numbers:
            # 規則 1: 排除 '0' (通常參考文獻從 1 開始)
            # 規則 2: 排除 '0' 開頭且長度 > 1 的 (如 '01', '001') -> 視情況，若您認為 '01' 算 '1' 則可用 int(num) 轉
            # 規則 3: 排除過長的數字 (如 '2023' 可能是年份，'00001' 可能是編號)
            # 這裡假設合理的參考文獻編號通常在 1~999 之間，或長度不超過 3 位數
            
            # 先轉成整數判斷數值
            val = int(num)
            
            # 條件 A: 數值必須 > 0
            if val == 0: continue
            
            # 條件 B: 排除像 [2024] 這種年份被誤判為引用的情況
            # 假設參考文獻不超過 2000 筆 (您可以根據需求放寬到 5000)
            if val > 2000: continue
            
            # 條件 C: 排除 '00001' 這種像流水號的格式 (雖然數值是 1)
            # 如果您想嚴格禁止 '01' 這種寫法，就檢查字串長度與數值是否匹配
            if num.startswith('0') and len(num) > 1: continue 
            
            extracted_numbers.append(str(val)) # 轉回標準字串 '1' (去掉 01 的 0)

        if not extracted_numbers: continue

        citation_id = f"{match.start()}-{match.end()}"
        if citation_id not in citation_ids:
            normalized = normalize_citation_for_matching(match.group(0))
            
            citations.append({
                'author': None,
                'co_author': None,
                'year': None,
                'ref_number': extracted_numbers[0], 
                'all_numbers': extracted_numbers,
                'original': match.group(0),
                'normalized': normalized,
                'position': match.start(),
                'type': 'IEEE-numeric',
                'format': 'IEEE'
            })
            citation_ids.add(citation_id)
            
    return citations