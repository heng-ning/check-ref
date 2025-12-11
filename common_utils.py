# 引入：
import re
import unicodedata
from docx import Document
import fitz  # PyMuPDF

# ===== 文字正規化工具 =====
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
    
    # 2. 關鍵字標準化 (方便 regex 統一抓取)
    # 將 "第xx卷" 轉為 "Vol. xx" 的形式讓後續邏輯通用，或者保留中文但在 regex 擴充
    # 這裡我們選擇保留中文關鍵字，但在主程式 regex 中擴充，比較安全
    
    return text.strip()

def has_chinese(text):
    """[NEW] 判斷字串是否包含中文字元"""
    return bool(re.search(r'[\u4e00-\u9fff]', text))

def extract_doi(text):
    """[NEW] 從文字中提取 DOI (通用，支援斷行和空格)"""
    # 方法1：處理 "doi: 10.xxxx" 或 "DOI: 10.xxxx" 格式
    doi_match = re.search(r'(?:doi:|DOI:)\s*(10\.\s*\d{4,}[^\s。]*(?:\s+[^\s。]+)*)', text, re.IGNORECASE)
    if doi_match:
        raw_doi = doi_match.group(1)
        clean_doi = re.sub(r'\s+', '', raw_doi)
        clean_doi = clean_doi.rstrip('。.,;')
        return clean_doi
    
    # 方法2：處理 "https://doi.org/10.xxxx" 格式（允許 https:// 和 doi.org/ 之間有空格）
    doi_start = re.search(r'https?:\s*//\s*doi\.org/', text, re.IGNORECASE)
    if doi_start:
        # 從 doi.org/ 後面開始抓取
        after_prefix = text[doi_start.end():]
        
        # 策略：從 10. 開始，積極抓取直到遇到明確的結束標記
        # 明確的結束標記：
        # 1. 連續兩個換行（段落分隔）
        # 2. 句號+換行+大寫字母開頭的新句子
        # 3. 新的文獻開始（作者格式：Last, F.）
        
        end_markers = [
            r'\n\s*\n',                          # 兩個換行（段落分隔）
            r'\.\s*\n\s*[A-Z][a-z]+,\s+[A-Z]\.', # 句號+換行+新文獻作者
        ]
        
        end_pos = len(after_prefix)
        for marker in end_markers:
            match = re.search(marker, after_prefix)
            if match and match.start() < end_pos:
                end_pos = match.start()
        
        # 提取 DOI 內容（可能包含空格、換行、句號內的斷行）
        doi_content = after_prefix[:end_pos]
        
        # 清理：移除所有空白字元（包括換行），保留 DOI 結構
        clean_doi = re.sub(r'\s+', '', doi_content)
        
        # 移除結尾的標點
        clean_doi = clean_doi.rstrip('。.,;')
        
        # 最終驗證：確保格式正確 (10.xxxx/xxxx)
        if re.match(r'10\.\d{4,}/.+', clean_doi):
            return clean_doi
    
    return None

def is_valid_year(year_str):
    try:
        year = int(year_str)
        return 1500 <= year <= 2050
    except:
        return False

# ===== 文件讀取 =====
def extract_paragraphs_from_docx(file):
    doc = Document(file)
    return [para.text.strip() for para in doc.paragraphs if para.text.strip()]

def extract_paragraphs_from_pdf(file):
    text = ""
    with fitz.open(stream=file.read(), filetype="pdf") as doc:
        for page in doc:
            text += page.get_text("text") + "\n"
    return [p.strip() for p in text.split("\n") if p.strip()]

# ===== 參考文獻區段識別 =====
def is_appendix_heading(text):
    """判斷是否為附錄標題"""
    text = text.strip()
    pattern = r'^([【〔（(]?\s*)?((\d+|[IVXLCDM]+|[一二三四五六七八九十壹貳參肆伍陸柒捌玖拾]+)[、．. ]?)?\s*(附錄|APPENDIX)(\s*[】〕）)]?)?$'
    return bool(re.match(pattern, text, re.IGNORECASE))

def is_reference_format(text):
    """判斷段落是否看起來像參考文獻"""
    text = text.strip()
    if len(text) < 10:
        return False
    if re.search(r'\(\d{4}[a-c]?\)', text):
        return True
    if re.match(r'^\[\d+\]', text):
        return True
    if re.search(r'[A-Z][a-z]+,\s*[A-Z]\.', text):
        return True
    return False

def extract_reference_section_improved(paragraphs):
    """
    [Enhanced] 參考文獻區段識別
    解決跨頁重複標題導致截斷的問題
    """
    reference_keywords = [
        "參考文獻", "參考資料", "references", "reference",
        "bibliography", "works cited", "literature cited",
        "references and citations"
    ]
    
    # 策略 1: 從後往前找，但找到標題後，要檢查是否為 "最後一個有效的標題"
    # 或者，如果發現多個標題，且它們之間都是參考文獻格式，則視為連續區塊
    
    # 我們先找出所有可能是 "參考文獻標題" 的索引
    ref_header_indices = []
    
    for i, para in enumerate(paragraphs):
        para = para.strip()
        if len(para) > 50: continue # 標題通常不長
        
        para_norm = normalize_text(para.lower())
        
        is_header = False
        # 1. 關鍵字完全匹配
        for kw in reference_keywords:
            if normalize_text(kw) == para_norm:
                is_header = True
                break
        
        # 2. Regex 匹配 (章節標題)
        if not is_header:
            pattern = r'^((第?[一二三四五六七八九十百千萬壹貳參肆伍陸柒捌玖拾佰仟萬]+章[、．.︑,，]?)|(\d+|[IVXLCDM]+)?[、．.︑,， ]?)?\s*(參考文獻|參考資料|references?|bibliography)\s*$'
            if re.match(pattern, para_norm):
                is_header = True
        
        if is_header:
            ref_header_indices.append(i)

    if not ref_header_indices:
        return [], None, "未找到參考文獻區段"

    # 策略調整：
    # 我們取 "第一個" 看起來像是真的開始的標題
    # 真標題的特徵：後面緊接著 [1] 或 1. 或 APA 格式
    
    start_index = -1
    for idx in ref_header_indices:
        # 檢查後面 5 行內是否有參考文獻格式
        check_range = paragraphs[idx+1 : min(idx+6, len(paragraphs))]
        if any(is_reference_format(p) for p in check_range):
            start_index = idx
            break
            
    # 如果沒找到明顯特徵，退回使用最後一個找到的標題
    if start_index == -1:
        start_index = ref_header_indices[-1]

    # 提取內容，並在過程中過濾掉重複的標題
    final_refs = []
    ref_keyword = paragraphs[start_index].strip()
    
    for i in range(start_index + 1, len(paragraphs)):
        para = paragraphs[i]
        
        # 1. 檢查是否為附錄 (停止點)
        if is_appendix_heading(para):
            break
            
        # 2. 檢查是否為重複出現的參考文獻標題 (跨頁頁眉) -> 跳過
        # 使用寬鬆匹配
        para_norm = normalize_text(para.lower().strip())
        is_duplicate_header = False
        for kw in reference_keywords:
            if normalize_text(kw) == para_norm:
                is_duplicate_header = True
                break
        
        if is_duplicate_header:
            continue # 跳過這行，繼續抓後面的文獻
            
        final_refs.append(para)

    return final_refs, ref_keyword, "改進版跨頁識別"

def extract_reference_section(paragraphs):
    """原本的簡單版本（fallback）"""
    reference_keywords = [
        "參考文獻", "參考資料", "references", "reference",
        "bibliography", "works cited", "literature cited"
    ]
    
    for i in reversed(range(len(paragraphs))):
        para = paragraphs[i].strip()
        para_lower = para.lower()
        para_normalized = normalize_text(para_lower)
        
        if len(para) > 50:
            continue
        
        for keyword in reference_keywords:
            if normalize_text(keyword) == para_normalized:
                ref_paragraphs = []
                for p in paragraphs[i + 1:]:
                    if is_appendix_heading(p):
                        break
                    ref_paragraphs.append(p)
                return ref_paragraphs, para, i
        
        pattern = r'^((第?[一二三四五六七八九十百千萬壹貳參肆伍陸柒捌玖拾佰仟萬]+章[、．.︑,，]?)|(\d+|[IVXLCDM]+)?[、．.︑,， ]?)?\s*(參考文獻|參考資料|references?|bibliography)\s*$'
        if re.match(pattern, para_lower):
            ref_paragraphs = []
            for p in paragraphs[i + 1:]:
                if is_appendix_heading(p):
                    break
                ref_paragraphs.append(p)
            return ref_paragraphs, para, i
    
    return [], None, None

def classify_document_sections(paragraphs):
    """將文件分為內文段落和參考文獻段落"""
    ref_paragraphs, ref_keyword, method = extract_reference_section_improved(paragraphs)
    
    if not ref_paragraphs:
        # Fallback (很少用到，但保留保險)
        return paragraphs, [], None, None
    
    # 反推開始位置 (因為 extract_reference_section_improved 邏輯變複雜了，不能簡單用 index)
    # 我們假設內容段落就是全部減去參考文獻部分
    # 但要注意，因為我們過濾掉了中間的重複標題，所以長度對不上
    
    # 簡單做法：找到 ref_keyword 第一次出現的位置 (start_index)
    # 在 extract_reference_section_improved 裡其實已經算過 start_index
    # 為了效能，這裡重新掃描一次 start_index 應該還好
    
    # 這裡有點小問題，因為我們不知道 improved 函式選了哪個 index
    # 讓我們修改 improved 函式讓它回傳 index 會更好，但為了不更動太多介面：
    
    # 重新尋找最佳切分點
    best_index = len(paragraphs) # Default to end
    
    # 使用與 improved 相同的邏輯找 start_index
    reference_keywords = [
        "參考文獻", "參考資料", "references", "reference",
        "bibliography", "works cited", "literature cited",
        "references and citations"
    ]
    
    for i, para in enumerate(paragraphs):
        para_norm = normalize_text(para.lower().strip())
        is_header = False
        for kw in reference_keywords:
            if normalize_text(kw) == para_norm:
                is_header = True; break
        if not is_header and re.match(r'^((第?[一]+章)|(\d+))?[、．. ]?\s*(參考文獻|references?)\s*$', para_norm):
            is_header = True
            
        if is_header:
            # 驗證
            check_range = paragraphs[i+1 : min(i+6, len(paragraphs))]
            if any(is_reference_format(p) for p in check_range):
                best_index = i
                break
                
    content_paragraphs = paragraphs[:best_index]
    
    return content_paragraphs, ref_paragraphs, best_index, ref_keyword

## 內文引用擷取
def extract_in_text_citations(content_paragraphs):
    full_text = " ".join(content_paragraphs)
    citations = []
    citation_ids = set()
    # APA: (作者, 年份) and 作者(年份) 型式
    pattern_apa1 = re.compile(
        r'(?<![0-9])[（(]\s*([\w\s\u4e00-\u9fff-]+?)\s*(?:(?:&|and|與|、)\s*([\w\s\u4e00-\u9fff-]+?))?\s*'
        r'(?:,?\s*et\s*al\.?)?\s*[,，]\s*(\d{4}[a-z]?)\s*[）)]',
        re.UNICODE | re.IGNORECASE
    )
    for match in pattern_apa1.finditer(full_text):
        author1 = match.group(1).strip()
        author2 = match.group(2).strip() if match.group(2) else None
        year = match.group(3)[:4]
        # 排除作者全為數字（如 14）
        if author1.isdigit():
            continue
        if is_valid_year(year):
            citation_id = f"{match.start()}-{match.end()}"
            if citation_id not in citation_ids:
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
    pattern_apa2 = re.compile(
        r'(?<![0-9])([\w\u4e00-\u9fff]+(?:\s+(?:et\s*al\.?|等))?)\s*[（(]\s*(\d{4}[a-z]?)\s*[）)]',
        re.UNICODE | re.IGNORECASE
    )
    for match in pattern_apa2.finditer(full_text):
        author = match.group(1).strip()
        year = match.group(2)[:4]
        # ========== [新增修正邏輯 START] ==========
        # 定義雜訊詞清單 (常用的學術連接詞)
        junk_prefixes = [
            # 5字以上
            '本研究不僅再次驗證', '這些觀點皆與', 
            
            # 4字
            '本研究採用', '此點亦與', 
            
            # 3字
            '而這與', '本研究', '也支持', '而在與', '這顯示',
            
            # 2字
            '根據', '依據', '參見', '參照', '此與', '亦與', '而這',
            '顯示', '指出', '發現', '認為', '以及', '至於', '反觀',
            
            # 1字 (最後才檢查單字)
            '如', '由', '採', '而', '與', '和', '及', '對', '故', 
            '經', '至', '則', '並', '但', '這'
        ]
        
        clean_author = author
        
        # 1. 迴圈清洗：移除開頭的雜訊詞
        keep_cleaning = True
        while keep_cleaning:
            keep_cleaning = False
            for prefix in junk_prefixes:
                if clean_author.startswith(prefix):
                    # 保護機制：確保移除後還有剩餘文字 (避免把姓氏 "與" 或 "嚴" 刪光)
                    if len(clean_author) > len(prefix):
                        clean_author = clean_author[len(prefix):].strip()
                        keep_cleaning = True 
                    break
        
        author = clean_author
        # ========== [新增修正邏輯 END] ============

        # 排除作者全為數字
        if author.isdigit():
            continue
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

