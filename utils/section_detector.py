import re

def is_appendix_heading(text):
    """判斷是否為附錄標題"""
    text = text.strip()
    # 支援：Appendix, 附錄, 附錄一, Appendix A
    pattern = r'^([【〔（(]?\s*)?((\d+|[IVXLCDM]+|[一二三四五六七八九十壹貳參肆伍陸柒捌玖拾]+)[、．. ]?)?\s*(附錄|APPENDIX)(\s*[】〕）)]?|(\s+[A-Z0-9]+))?$'
    return bool(re.match(pattern, text, re.IGNORECASE))

def is_reference_heading_flexible(text):
    """
    判斷：單行是否為參考文獻標題
    能抓到：'Reference', 'References', '柒、參考文獻', '7. 參考文獻'
    """
    text = text.strip().lower()
    if len(text) > 40: return False # 太長通常是內文

    # 核心關鍵字 regex
    keywords_regex = r'(references?|bibliography|works cited|literature cited|參考文獻|參考資料|參考書目|文獻列表)'

    # 前綴積木：抓取 "陸、", "7.", "VII.", "第一章", "[1]"
    prefix_pattern = r'^(' \
                     r'\s*[\(【\[]?\s*' \
                     r'(?:第?[0-9\.]+|[ivxlcdm]+|[一二三四五六七八九十百千萬壹貳參肆伍陸柒捌玖拾佰仟萬]+)' \
                     r'(?:章)?' \
                     r'\s*[\)\]】]?' \
                     r')?'

    # 分隔積木：抓取空格、點、頓號
    delimiter_pattern = r'[\s\.\、\,:：\-\_]*'

    # 組合 regex：前綴 + 分隔 + 關鍵字 + (結尾容許少量雜訊)
    full_pattern = prefix_pattern + delimiter_pattern + keywords_regex + r'.*$'
    
    return bool(re.match(full_pattern, text))

def is_pure_prefix(text):
    """
    判斷是否為「純前綴」 (用於解決斷行標題：陸、)
    例如：'陸、', 'VII.', '7.', '第一章'
    """
    text = text.strip()
    if len(text) > 10: return False
    # 必須符合前綴格式 (數字/羅馬/中文數字 + 標點)
    pattern = r'^[\(【\[]?(?:第?[0-9\.]+|[IVXLCDMivxlcdm]+|[一二三四五六七八九十百千萬壹貳參肆伍陸柒捌玖拾佰仟萬]+)(?:章)?[\)\]】]?[\s\.\、\,:：\-\_]*$'
    return bool(re.match(pattern, text))

def is_pure_keyword(text):
    """
    判斷是否為「純關鍵字」 (用於解決斷行標題的下一行)
    例如：'參考文獻', 'References'
    """
    text = text.strip().lower()
    if len(text) > 20: return False
    keywords = ["參考文獻", "參考資料", "references", "reference", "bibliography", "works cited"]
    # 移除常見標點後比對
    clean_text = re.sub(r'[^\w\u4e00-\u9fff]', '', text)
    return clean_text in keywords

def extract_reference_section_improved(paragraphs):
    """
    支援斷行標題 (陸、\\n參考文獻) 與子標題保留
    """
    ref_start_index = -1
    ref_keyword = None
    
    # --- 步驟 1: 尋找標題 (由後往前找，避免抓到目錄) ---
    n = len(paragraphs)
    for i in range(n - 1, -1, -1):
        para = paragraphs[i].strip()
        if not para: continue
        
        # 情況 A: 標準單行標題
        if is_reference_heading_flexible(para):
            ref_start_index = i
            ref_keyword = para
            break
            
        # 情況 B: 斷行標題
        if i + 1 < n:
            next_para = paragraphs[i+1].strip()
            if is_pure_prefix(para) and is_pure_keyword(next_para):
                ref_start_index = i
                ref_keyword = para + " " + next_para
                break

    if ref_start_index == -1:
        return [], None, "未找到參考文獻區段"

    # --- 步驟 2: 提取內容 ---
    final_refs = []
    
    # 設定開始抓取的下一行
    start_capture_idx = ref_start_index + 1
    
    # 如果是斷行標題 (情況 B)，下一行是 "參考文獻" 關鍵字，也要跳過
    if start_capture_idx < n and is_pure_keyword(paragraphs[start_capture_idx]):
        start_capture_idx += 1

    for i in range(start_capture_idx, n):
        para = paragraphs[i].strip()
        
        if not para: continue
        
        # 1. 遇到附錄或作者簡介 -> 停止
        if is_appendix_heading(para) or re.match(r'^([0-9\.]+|[ivxlcdm]+)?\s*[\.\、\s]*(biography|about the author|作者簡介)', para, re.IGNORECASE):
            break
            
        # 2. 過濾掉重複的參考文獻標題 (跨頁頁眉)
        if is_reference_heading_flexible(para):
            continue

        # 3. 過濾掉單獨的頁碼 (如 "59", "60")
        if re.match(r'^\d{1,3}\s*$', para):
            continue

        final_refs.append(para)

    return final_refs, ref_keyword, "增強版標題識別(含斷行)"

def extract_reference_section(paragraphs):
    return extract_reference_section_improved(paragraphs)

def classify_document_sections(paragraphs):
    """
    將文件分為內文段落和參考文獻段落
    使用與 extract_reference_section_improved 一致的寬鬆判斷邏輯
    """
    # 1. 先嘗試提取參考文獻
    ref_paragraphs, ref_keyword, method = extract_reference_section_improved(paragraphs)
    
    if not ref_paragraphs:
        return paragraphs, [], None, None
    
    # 2. 尋找最佳切分點 (Split Index)
    best_index = len(paragraphs) 
    
    # 由後往前找，找到「最後一個」符合我們萬用標題邏輯的地方
    n = len(paragraphs)
    for i in range(n - 1, -1, -1):
        para = paragraphs[i].strip()
        if not para: continue
        
        if is_reference_heading_flexible(para):
            best_index = i
            break
            
        # 斷行標題判斷
        if i + 1 < n:
            next_para = paragraphs[i+1].strip()
            if is_pure_prefix(para) and is_pure_keyword(next_para):
                best_index = i
                break

    # 3. 執行切分
    content_paragraphs = paragraphs[:best_index]
    
    return content_paragraphs, ref_paragraphs, best_index, ref_keyword

