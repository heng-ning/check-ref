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

        #category_keywords = r'(Conference|Journal|Article|Preprint|Paper|Book|Theses|Dissertation|Report|Proceedings|Symposium|Web|Online)'
        #if re.match(r'^\d+\.\s*' + category_keywords, para, re.IGNORECASE):
            #if len(para) < 50:
               # continue
        if re.match(r'^\d+$', para) or re.match(r'^\[source', para, re.IGNORECASE): continue
        if re.match(r'^(Table|Figure|Fig\.)', para, re.IGNORECASE): continue
        category_keywords = r'(中文|英文|一|二|三|四|五|期刊論文|學術研討會論文|網站文章|Conference|Journal|Article|Preprint|Paper|Book|Theses|Dissertation|Report|Proceedings|Symposium|Web|Online)'
        if re.match(r'^[\d\.\s、，,：:\[\]一二三四五]*' + category_keywords, para, re.IGNORECASE):
            if len(para) < 50:
                if not re.search(r'[（(]\s*\d{4}', para): 
                    if not re.search(r'(Journal of|Proceedings of)', para, re.IGNORECASE):
                        continue
        if re.match(r'^\d+\.\s*[A-Za-z\s/&]+$', para) and len(para) < 60:
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
            #elif re.match(r'^\d{1,3}\.\s*$', para):
             #   is_new_start = False
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
        if is_new_start and current_ref:
            # 如果暫存區只有 "數字." (例如 "1.")，代表上一行是被斷開的編號
            if re.match(r'^\d+\.\s*$', current_ref):
                is_new_start = False   # 取消新文獻判定
                is_continuation = True # 強制視為延續
        # 4. 執行動作
        # 4. 執行動作
        if is_new_start:
            if current_ref: merged.append(current_ref)
            # 【修正 1】針對 "6. Putra"：放寬移除條件
            # 只要是 "1~3位數字 + 點" 開頭 (例如 1. 或 999.)，後面不管接什麼，都把編號跟空白去掉
            if re.match(r'^\d{1,3}\.\s*', para):
                para = re.sub(r'^\d{1,3}\.\s*', '', para) # 【修正 2】針對 "Waqar,A."：補上逗號後的空白，# 如果發現 "小寫字母,大寫字母" (例如 r,A)，中間補一個空白變成 "r, A"， # 這樣後續的作者判斷程式就能讀懂了
            para = re.sub(r'([a-z]),([A-Z])', r'\1, \2', para)
            current_ref = para
        elif is_continuation:
            if current_ref:# 處理中文與英文的連接空白
                if has_chinese(current_ref[-1:]) and has_chinese(para[:1]):
                    current_ref += para
                else:
                    current_ref += " " + para
            else:
                current_ref = para
        else: # 既不是新開始，也不是明顯的延續 (預設合併)
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
    
    # 修復 URL 斷行問題
    # 例如: "https://example.com/path- abc123" → "https://example.com/path-abc123"
    fixed_merged = []
    for ref in merged:
        # 移除 URL 中間的空格和換行（連字符後的空格）
        ref = re.sub(r'(https?://[^\s]*?)-\s+([a-zA-Z0-9])', r'-\1\2', ref)
        ref = re.sub(r'(https?://[^\s]*?)\s+([a-zA-Z0-9/_\-]+)', r'\1\2', ref)
        fixed_merged.append(ref)
    
    return fixed_merged
