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
    """改進的參考文獻區段識別 (維持原本較強大的邏輯，包含附錄排除)"""
    reference_keywords = [
        "參考文獻", "參考資料", "references", "reference",
        "bibliography", "works cited", "literature cited",
        "references and citations"
    ]
    
    def clip_until_stop(paragraphs_after):
        """截取至附錄為止"""
        result = []
        for para in paragraphs_after:
            if is_appendix_heading(para):
                break
            result.append(para)
        return result
    
    for i in reversed(range(len(paragraphs))):
        para = paragraphs[i].strip()
        para_lower = para.lower()
        para_normalized = normalize_text(para_lower)
        
        if len(para) > 50:
            continue
        
        for keyword in reference_keywords:
            if normalize_text(keyword) == para_normalized:
                return clip_until_stop(paragraphs[i + 1:]), para, "純標題識別"
        
        pattern = r'^((第?[一二三四五六七八九十百千萬壹貳參肆伍陸柒捌玖拾佰仟萬]+章[、．.︑,，]?)|(\d+|[IVXLCDM]+)?[、．.︑,， ]?)?\s*(參考文獻|參考資料|references?|bibliography)\s*$'
        if re.match(pattern, para_lower):
            return clip_until_stop(paragraphs[i + 1:]), para, "章節標題識別"
        
        fuzzy_keywords = ["reference", "參考", "bibliography"]
        if any(para_lower.strip() == k for k in fuzzy_keywords):
            if i + 1 < len(paragraphs):
                next_paras = paragraphs[i+1:min(i+6, len(paragraphs))]
                if sum(1 for p in next_paras if is_reference_format(p)) >= 1:
                    return clip_until_stop(paragraphs[i + 1:]), para.strip(), "內容特徵識別"
    
    return [], None, "未找到參考文獻區段"

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
        ref_paragraphs, ref_keyword, _ = extract_reference_section(paragraphs)
        if not ref_paragraphs:
            return paragraphs, [], None, None
    
    ref_start_index = None
    for i, para in enumerate(paragraphs):
        if para.strip() == ref_keyword:
            ref_start_index = i
            break
    
    if ref_start_index is None:
        # Fallback if keyword index not found exactly
        ref_start_index = len(paragraphs) - len(ref_paragraphs)
    
    content_paragraphs = paragraphs[:ref_start_index]
    return content_paragraphs, ref_paragraphs, ref_start_index, ref_keyword

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

