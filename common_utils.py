# common_utils.py
import re
import unicodedata
from docx import Document
import fitz  # PyMuPDF

# =============================================================================
# 1. 文字正規化與基礎工具
# =============================================================================

def normalize_text(text):
    """正規化文字：全形轉半形、清理各種空白與控制符"""
    if not text:
        return ""
    # 1️⃣ 全形字元轉半形 (包含括號、標點、空格)
    text = unicodedata.normalize('NFKC', text)
    # 2️⃣ 將常見隱藏空白（NBSP、全形空白等）統一為一般空白
    text = re.sub(r'[\u3000\xa0\u200b\u200c\u200d]+', ' ', text)
    # 3️⃣ 去除多重空白、換行、tab
    text = re.sub(r'\s+', ' ', text)
    # 4️⃣ 去頭尾空白
    return text.strip()

def normalize_citation_for_matching(citation):
    """專門用於引用比對的正規化"""
    text = normalize_text(citation)
    text = re.sub(r'\s', '', text)
    text = text.replace('（', '(').replace('）', ')')
    text = text.replace('【', '[').replace('】', ']')
    return text.lower()

def normalize_chinese_text(text):
    """
    將中文文獻常見的全形標點與關鍵字，轉換為程式易於解析的通用格式
    """
    # 1. 標點符號標準化
    text = text.replace('，', ', ').replace('：', ': ').replace('；', '; ')
    text = text.replace('。', '. ').replace('（', '(').replace('）', ')')
    text = text.replace('「', '“').replace('」', '”')
    text = text.replace('、', ', ') # 作者分隔
    return text.strip()

def has_chinese(text):
    """判斷字串是否包含中文字元"""
    return bool(re.search(r'[\u4e00-\u9fff]', text))

def extract_doi(text):
    """從文字中提取 DOI (通用，支援斷行和空格)"""
    # 方法1：處理 "doi: 10.xxxx" 或 "DOI: 10.xxxx" 格式
    doi_match = re.search(r'(?:doi:|DOI:)\s*(10\.\s*\d{4,}[^\s。]*(?:\s+[^\s。]+)*)', text, re.IGNORECASE)
    if doi_match:
        raw_doi = doi_match.group(1)
        clean_doi = re.sub(r'\s+', '', raw_doi)
        clean_doi = clean_doi.rstrip('。.,;')
        return clean_doi
    
    # 方法2：處理 "https://doi.org/10.xxxx" 格式
    doi_start = re.search(r'https?:\s*//\s*doi\.org/', text, re.IGNORECASE)
    if doi_start:
        after_prefix = text[doi_start.end():]
        # 策略：從 10. 開始，積極抓取直到遇到明確的結束標記
        end_markers = [
            r'\n\s*\n',                                  # 兩個換行
            r'\.\s*\n\s*[A-Z][a-z]+,\s+[A-Z]\.',         # 句號+換行+新文獻作者
        ]
        end_pos = len(after_prefix)
        for marker in end_markers:
            match = re.search(marker, after_prefix)
            if match and match.start() < end_pos:
                end_pos = match.start()
        
        doi_content = after_prefix[:end_pos]
        clean_doi = re.sub(r'\s+', '', doi_content)
        clean_doi = clean_doi.rstrip('。.,;')
        
        if re.match(r'10\.\d{4,}/.+', clean_doi):
            return clean_doi
    return None

def is_valid_year(year_str):
    try:
        year = int(year_str)
        return 1500 <= year <= 2050
    except:
        return False

# =============================================================================
# 2. 文件讀取
# =============================================================================

def extract_paragraphs_from_docx(file):
    doc = Document(file)
    return [para.text.strip() for para in doc.paragraphs if para.text.strip()]

def extract_paragraphs_from_pdf(file):
    text = ""
    with fitz.open(stream=file.read(), filetype="pdf") as doc:
        for page in doc:
            text += page.get_text("text") + "\n"
    return [p.strip() for p in text.split("\n") if p.strip()]

# =============================================================================
# 3. 參考文獻區段識別 (核心修改區域)
# =============================================================================

def is_appendix_heading(text):
    """判斷是否為附錄標題"""
    text = text.strip()
    # 支援：Appendix, 附錄, 附錄一, Appendix A
    pattern = r'^([【〔（(]?\s*)?((\d+|[IVXLCDM]+|[一二三四五六七八九十壹貳參肆伍陸柒捌玖拾]+)[、．. ]?)?\s*(附錄|APPENDIX)(\s*[】〕）)]?|(\s+[A-Z0-9]+))?$'
    return bool(re.match(pattern, text, re.IGNORECASE))

def is_reference_heading_flexible(text):
    """
    [NEW] 萬用判斷：單行是否為參考文獻標題
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
    [NEW] 判斷是否為「純前綴」 (用於解決斷行標題：陸、)
    例如：'陸、', 'VII.', '7.', '第一章'
    """
    text = text.strip()
    if len(text) > 10: return False
    # 必須符合前綴格式 (數字/羅馬/中文數字 + 標點)
    pattern = r'^[\(【\[]?(?:第?[0-9\.]+|[IVXLCDMivxlcdm]+|[一二三四五六七八九十百千萬壹貳參肆伍陸柒捌玖拾佰仟萬]+)(?:章)?[\)\]】]?[\s\.\、\,:：\-\_]*$'
    return bool(re.match(pattern, text))

def is_pure_keyword(text):
    """
    [NEW] 判斷是否為「純關鍵字」 (用於解決斷行標題的下一行)
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
    [Updated] 增強版：支援斷行標題 (陸、\\n參考文獻) 與子標題保留
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
    """原本的簡單版本 (保留作為 Fallback)"""
    return extract_reference_section_improved(paragraphs)

def classify_document_sections(paragraphs):
    """
    [Updated] 將文件分為內文段落和參考文獻段落
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
        
        # 使用我們剛剛定義的萬用判斷函式
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

# =============================================================================
# 4. 內文引用擷取
# =============================================================================

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
                    r'([\w\s\u4e00-\u9fff&,、-]+?(?:\s+(?:et\s*al\.?|等))?)\s*[,，]\s*(\d{4}[a-z]?)', 
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
        r'(?<![0-9])[（(]\s*([\w\s\u4e00-\u9fff-]+?)\s*(?:(?:&|and|與|、)\s*([\w\s\u4e00-\u9fff-]+?))?\s*'
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
        r'(?<![0-9])([\w\u4e00-\u9fff]+(?:\s+(?:et\s*al\.?|等))?)\s*[（(]\s*(\d{4}[a-z]?)\s*[）)]',
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
            '顯示', '指出', '發現', '認為', '以及', '至於', '反觀',
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