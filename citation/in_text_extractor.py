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
            '本研究不僅再次驗證', '這些觀點皆與', '本研究採用', '此點亦與', 
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
    pattern_ieee = re.compile(r'[【\[]\s*(\d+)\s*[】\]]', re.UNICODE)
    for match in pattern_ieee.finditer(full_text):
        ref_number = match.group(1)
        citation_id = f"{match.start()}-{match.end()}"
        if citation_id not in citation_ids:
            normalized = normalize_citation_for_matching(match.group(0))
            citations.append({
                'author': None,
                'co_author': None,
                'year': None,
                'ref_number': ref_number,
                'original': match.group(0),
                'normalized': normalized,
                'position': match.start(),
                'type': 'IEEE-numeric',
                'format': 'IEEE'
            })
            citation_ids.add(citation_id)
            
    return citations