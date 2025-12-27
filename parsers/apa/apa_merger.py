import re
from utils.text_processor import (
    normalize_text,
    has_chinese
)

def find_apa_head(ref_text):
    """偵測 APA 格式開頭 (含變體格式)"""
    match = re.search(r'[（(]\s*(\d{4}(?:[a-z])?|n\.d\.)\s*(?:,\s*([A-Za-z]+\.?\s*\d{0,2}))?\s*[)）]', ref_text)
    if match and match.start() < 80: return True
    
    match_comma = re.search(r'[\.,]\s*(\d{4}(?:[a-z])?)\s*[\.,]', ref_text)
    if match_comma and match_comma.start() < 80: return True
    
    return False

def merge_references_unified(paragraphs):
    """
    通用合併邏輯：
    1. 過濾分類標題
    2. 判斷新文獻開始 (增加數值大小防呆，避免文章編號 104979. 被誤判)
    3. 判斷延續
    """
    merged = []
    current_ref = ""
    
    for para in paragraphs:
        para = normalize_text(para)
        if not para: continue

        # 1. 過濾分類標題
        category_keywords = r'(Conference|Journal|Article|Preprint|Paper|Book|Theses|Dissertation|Report|Proceedings|Symposium|Web|Online)'
        if re.match(r'^\d+\.\s*' + category_keywords, para, re.IGNORECASE):
            if len(para) < 50:
                continue

        # 2. 判斷是否為新文獻開始 (Priority High)
        is_new_start = False
        
        # A. 中文標準
        if re.match(r'^[\u4e00-\u9fa5]+.*?[\(（]\d{4}[\)）]', para):
            is_new_start = True
            
        # B. 英文標準
        elif re.match(r'^[A-Z][^\d\(\)]+(\(|\,\s*)\d{4}', para) and not re.match(r'^\s*(&|and)\b', para, re.IGNORECASE):
            is_new_start = True
            
        # C. 法規文獻（標題開頭 + 括號日期）
        elif re.match(r'^[\u4e00-\u9fa5]+.*?[\(（]\d{4}\s*年', para):
            is_new_start = True

        # D. 編號開頭 (修正：避免文章編號與頁碼誤判)
        elif re.match(r'^(\d+)\.', para):
            num_match = re.match(r'^(\d+)', para)
            num_val = int(num_match.group(1))
            
            # 防呆條件 1: 數字 > 500 通常是文章編號
            if num_val > 500:
                is_new_start = False
            # 防呆條件 2: 數字後面緊接 DOI 或 URL
            elif re.search(r'^\d+\.\s*(https?://|doi:)', para, re.IGNORECASE):
                is_new_start = False
            # 防呆條件 3: 純粹只有數字+句號（如 "162."），可能是頁碼
            elif re.match(r'^\d{1,3}\.\s*$', para):
                is_new_start = False
            else:
                is_new_start = True
        
        # D. IEEE 括號編號 [1]
        elif re.match(r'^\s*[\[【]\s*\d+\s*[】\]]', para):
            is_new_start = True

        # 3. 判斷是否為延續 (Priority Low)
        is_continuation = False
        if not is_new_start:
            # A. 包含 DOI 或 arXiv
            if re.search(r'(doi:10\.|doi\.org|arXiv:)', para, re.IGNORECASE):
                is_continuation = True
            # B. 會議資訊 (全大寫+年份)
            elif re.match(r'^([A-Z]{2,}(?:\s+[A-Z]{2,})*)\s+\d{4}', para):
                is_continuation = True
            # C. 特殊出版資訊
            elif re.match(r'^(Paper No\.|Vol\.|pp\.|no\.)', para, re.IGNORECASE):
                is_continuation = True
            # D. 大數字開頭的行 (如 104979.) 也視為延續
            elif re.match(r'^\d{4,}\.', para):
                is_continuation = True

        # 4. 執行動作
        if is_new_start:
            if current_ref: merged.append(current_ref)
            current_ref = para
        elif is_continuation:
            if current_ref:
                if has_chinese(current_ref[-1:]) and has_chinese(para[:1]):
                    current_ref += para
                else:
                    current_ref += " " + para
            else:
                current_ref = para
        else:
            if current_ref:
                if has_chinese(current_ref[-1:]) and has_chinese(para[:1]):
                    current_ref += para
                elif current_ref.endswith('-'):
                    if para and para[0].islower():
                        current_ref = current_ref[:-1] + para
                    else:
                        current_ref = current_ref + " " + para
                else:
                    current_ref += " " + para
            else:
                current_ref = para
                
    if current_ref: merged.append(current_ref)
    return merged
