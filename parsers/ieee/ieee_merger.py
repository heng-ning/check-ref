import re
from utils.text_processor import has_chinese

def merge_references_ieee_strict(paragraphs):
    """
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
                current_ref = para
                
    if current_ref: merged.append(current_ref)
    return merged
