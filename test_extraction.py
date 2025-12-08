import streamlit as st
import re
import unicodedata
from docx import Document
import fitz  # PyMuPDF
import json
from datetime import datetime

# ==================== 0. 文字正規化工具 ====================

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

# ========== [NEW] test1201 新增的輔助函式 ==========
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
    
    # 方法2：處理 "https://doi.org/10.xxxx" 格式（關鍵修正）
    doi_start = re.search(r'https?://doi\.org/', text, re.IGNORECASE)
    if doi_start:
        # 從 doi.org/ 後面開始抓取
        after_prefix = text[doi_start.end():]
        
        # 策略：從 10. 開始，一直抓到遇到「明確的結束標記」為止
        # 明確的結束標記：連續兩個換行、句號+空格+大寫字母、或文末
        
        # 先找到 DOI 的結束位置
        end_markers = [
            r'\n\s*\n',           # 兩個換行（段落分隔）
            r'\.\s+[A-Z]',        # 句號+空格+大寫（下一句開始）
            r'[。，]\s',          # 中文標點+空格
        ]
        
        end_pos = len(after_prefix)
        for marker in end_markers:
            match = re.search(marker, after_prefix)
            if match and match.start() < end_pos:
                end_pos = match.start()
        
        # 提取 DOI 內容（可能包含空格、換行）
        doi_content = after_prefix[:end_pos]
        
        # 清理：只保留 10.xxxx/xxxx 部分
        # 允許數字、字母、點、斜線、連字號，以及中間的空格
        doi_pattern = re.match(r'(10\.\S+(?:\s+\S+)*?)(?=\s*$)', doi_content)
        if doi_pattern:
            raw_doi = doi_pattern.group(1)
            # 移除所有空白字元
            clean_doi = re.sub(r'\s+', '', raw_doi)
            # 移除結尾的標點
            clean_doi = clean_doi.rstrip('。.,;')
            
            # 最終驗證：確保格式正確 (10.xxxx/xxxx)
            if re.match(r'10\.\d{4,}/.+', clean_doi):
                return clean_doi
    
    return None

# =================================================

# ==================== 1. 文件讀取模組 ====================

def extract_paragraphs_from_docx(file):
    doc = Document(file)
    return [para.text.strip() for para in doc.paragraphs if para.text.strip()]

def extract_paragraphs_from_pdf(file):
    text = ""
    with fitz.open(stream=file.read(), filetype="pdf") as doc:
        for page in doc:
            text += page.get_text("text") + "\n"
    return [p.strip() for p in text.split("\n") if p.strip()]

# ==================== 2. 參考文獻區段識別 ====================

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


# ==================== 3. 內文引用擷取 ====================

def is_valid_year(year_str):
    try:
        year = int(year_str)
        return 1500 <= year <= 2050
    except:
        return False

def extract_in_text_citations(content_paragraphs):
    """
    修正：APA 內文引用不抓數字作者，排除如 14(2022)
    """
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

# ==================== 4. 參考文獻解析 (舊版 1204 邏輯 - 已註解保留) ====================

## [舊程式碼 1204 - 斷行合併與特徵偵測]
## 這些功能已被 test1201 的 merge_references_unified (進階版) 取代
## def find_apa(ref_text):
##     """
##     改進：支援 (2007, October 11) / (2011, Jan. 14) / (n.d.)
##     """
##     ref_text = normalize_text(ref_text)
##
##     apa_match = re.search(
##         r'[（(]\s*(\d{4}(?:[a-c])?|n\.d\.)\s*(?:,\s*(?:[A-Za-z]+\.?\s*\d{0,2}))?\s*[)）]',
##         ref_text, re.IGNORECASE
##     )
##
##     if not apa_match:
##         return False
##
##     year_str = apa_match.group(1)[:4]
##     year_pos = apa_match.start(1)
##     pre_context = ref_text[max(0, year_pos - 5):year_pos]
##     if re.search(r'\d', pre_context):  # 避免 887(2020) 誤判
##         return False
##
##     return year_str.isdigit() or apa_match.group(1).lower() == "n.d."
##
## def find_apalike(ref_text):
##     valid_years = []
##     for match in re.finditer(r'[,，.。]\s*(\d{4}[a-c]?)[.。，]', ref_text):
##         year_str = match.group(1)
##         year_pos = match.start(1)
##         year_core = year_str[:4]
##         if not is_valid_year(year_core): continue
##         pre_context = ref_text[max(0, year_pos - 5):year_pos]
##         if re.search(r'\d', pre_context): continue
##         after_context = ref_text[match.end(1):match.end(1) + 5]
##         if re.match(r'\.(\d{1,2}|[a-z0-9]{2,})', after_context, re.IGNORECASE): continue
##         arxiv_pattern = re.compile(
##             r'arxiv:\d{4}\.\d{5}[^a-zA-Z0-9]{0,3}\s*[,，]?\s*' + re.escape(year_str), re.IGNORECASE
##         )
##         if arxiv_pattern.search(ref_text) and arxiv_pattern.search(ref_text).start() < year_pos: continue
##         valid_years.append((year_str, year_pos))
##     for match in re.finditer(r'，\s*(\d{4}[a-c]?)\s*，\s*。', ref_text):
##         year_str = match.group(1)
##         year_pos = match.start(1)
##         year_core = year_str[:4]
##         if not is_valid_year(year_core): continue
##         pre_context = ref_text[max(0, year_pos - 5):year_pos]
##         if re.search(r'\d', pre_context): continue
##         valid_years.append((year_str, year_pos))
##     return valid_years
##
## def is_reference_head(para):
##     return bool(find_apa(para) or re.match(r"^\[\d+\]", para) or find_apalike(para))
##
## def find_apa_matches(ref_text):
##     APA_PATTERN = r'[（(](\d{4}[a-c]?|n\.d\.)\s*(?:,\s*[A-Za-z]+\s*\d{1,2})?\s*[）)]?[。\.]?'
##     matches = []
##     for m in re.finditer(APA_PATTERN, ref_text, re.IGNORECASE):
##         year_str = m.group(1)[:4]
##         year_pos = m.start(1)
##         pre_context = ref_text[max(0, year_pos - 5):year_pos]
##         if re.search(r'\d', pre_context): continue
##         if year_str.isdigit() and is_valid_year(year_str):
##             matches.append(m)
##         elif m.group(1).lower() == "n.d.":
##             matches.append(m)
##     return matches
##
## def find_apalike_matches(ref_text):
##     matches = []
##     pattern1 = r'[,，.。]\s*(\d{4}[a-c]?)[.。，]'
##     for m in re.finditer(pattern1, ref_text):
##         year_str = m.group(1)
##         year_pos = m.start(1)
##         year_core = year_str[:4]
##         if not is_valid_year(year_core): continue
##         pre_context = ref_text[max(0, year_pos - 5):year_pos]
##         after_context = ref_text[m.end(1):m.end(1) + 5]
##         if re.search(r'\d', pre_context): continue
##         if re.match(r'\.(\d{1,2}|[a-z0-9]{2,})', after_context, re.IGNORECASE): continue
##         arxiv_pattern = re.compile(
##             r'arxiv:\d{4}\.\d{5}[^a-zA-Z0-9]{0,3}\s*[,，]?\s*' + re.escape(year_str), re.IGNORECASE
##         )
##         if arxiv_pattern.search(ref_text) and arxiv_pattern.search(ref_text).start() < year_pos: continue
##         matches.append(m)
##     pattern2 = r'，\s*(\d{4}[a-c]?)\s*，\s*。'
##     for m in re.finditer(pattern2, ref_text):
##         year_str = m.group(1)
##         year_pos = m.start(1)
##         year_core = year_str[:4]
##         pre_context = ref_text[max(0, year_pos - 5):year_pos]
##         if re.search(r'\d', pre_context): continue
##         if is_valid_year(year_core):
##             matches.append(m)
##     return matches
##
## def split_multiple_apa_in_paragraph(paragraph):
##     apa_matches = find_apa_matches(paragraph)
##     apalike_matches = find_apalike_matches(paragraph)
##     all_matches = apa_matches + apalike_matches
##     all_matches.sort(key=lambda m: m.start())
##     if len(all_matches) < 2:
##         return [paragraph]
##     split_indices = []
##     for match in all_matches[1:]:
##         cut_index = max(0, match.start() - 5)
##         split_indices.append(cut_index)
##     segments = []
##     start = 0
##     for idx in split_indices:
##         segments.append(paragraph[start:idx].strip())
##         start = idx
##     segments.append(paragraph[start:].strip())
##     return [s for s in segments if s]
##
## def merge_references_by_heads(paragraphs):
##     merged = []
##     for para in paragraphs:
##         apa_count = 1 if find_apa(para) else 0
##         apalike_count = len(find_apalike(para))
##         if apa_count >= 2 or apalike_count >= 2:
##             sub_refs = split_multiple_apa_in_paragraph(para)
##             merged.extend([s.strip() for s in sub_refs if s.strip()])
##         else:
##             if is_reference_head(para):
##                 merged.append(para.strip())
##             else:
##                 if merged:
##                     merged[-1] += " " + para.strip()
##                 else:
##                     merged.append(para.strip())
##     return merged
##
## def detect_reference_format(ref_text):
##     """偵測參考文獻格式"""
##     if re.match(r'^\s*[【\[]\s*\d+\s*[】\]]\s*', ref_text):
##         return 'IEEE'
##     
##     if find_apa(ref_text):
##         return 'APA'
##     
##     if find_apalike(ref_text):
##         return 'APA_LIKE'
##     
##     return 'Unknown'


# ==================== [修正版：IEEE 文獻資訊擷取] - 已註解保留 ====================

## def extract_ieee_reference_info_fixed(ref_text):
##     """修正版 IEEE 格式擷取（修復多作者問題）"""
##     
##     number_match = re.match(r'^\s*[\[【]\s*(\d+)\s*[\]】]\s*', ref_text)
##     if not number_match:
##         return None
##     
##     ref_number = number_match.group(1)
##     rest_text = ref_text[number_match.end():].strip()
##     
##     authors = "Unknown"
##     title = None
##     year = "Unknown"
##     
##     # 步驟 1：優先找引號中的標題
##     quote_patterns = [
##         (r'"', r'"'),
##         (r'“', r'”'),
##         (r'「', r'」'),
##         (r'\'', r'\''),
##         (r'“', r'“'),
##         (r'”', r'”'),
##     ]
##     
##     title_found = False
##     
##     for open_q, close_q in quote_patterns:
##         pattern = re.escape(open_q) + r'(.+?)' + re.escape(close_q)
##         match = re.search(pattern, rest_text)
##         
##         if match:
##             title = match.group(1).strip()
##             title = re.sub(r'[,，.。;；:：]*$', '', title).strip()
##             
##             # 引號前的所有內容都是作者（包含多作者）
##             before_title = rest_text[:match.start()].strip()
##             before_title = before_title.rstrip(',，. ')
##             
##             # 移除可能的 "and" 結尾
##             before_title = re.sub(r'\s+and\s*$', '', before_title, flags=re.IGNORECASE)
##             # 移除 et al. 結尾
##             before_title = re.sub(r',?\s*et\s+al\.?$', '', before_title, flags=re.IGNORECASE)
##             
##             if before_title:
##                 # 清理開頭的編號殘留
##                 before_title = re.sub(r'^\[\d+\]\s*', '', before_title)
##                 
##                 # 完整保留所有作者（用逗號分隔的多作者）
##                 if re.search(r'[a-zA-Z\u4e00-\u9fff]', before_title) and len(before_title) > 1:
##                     authors = before_title  # 保留完整多作者字串
##             
##             title_found = True
##             break
##     
##     # 如果沒有找到引號標題，用備選方案
##     if not title_found:
##         # 嘗試用 "and" 判斷作者區段結尾
##         and_match = re.search(r'\band\b', rest_text, re.IGNORECASE)
##         
##         if and_match:
##             after_and = rest_text[and_match.end():].strip()
##             next_comma = after_and.find(',')
##             
##             if next_comma > 0:
##                 # 從開頭到 "and" 後第一個逗號為作者
##                 authors_section = rest_text[:and_match.end() + next_comma].strip()
##                 authors_section = authors_section.rstrip(',，. ')
##                 
##                 # 完整保留作者區段
##                 if authors_section and re.search(r'[a-zA-Z]', authors_section):
##                     authors = authors_section
##                 
##                 # 逗號後的內容為標題候選
##                 remaining = rest_text[and_match.end() + next_comma:].strip()
##                 remaining = remaining.lstrip(',，. ')
##                 
##                 title_match = re.match(r'^([^,，.。]+)', remaining)
##                 if title_match:
##                     potential_title = title_match.group(1).strip()
##                     if len(potential_title) > 10:
##                         title = potential_title
##         else:
##             # 沒有 "and"，嘗試用第一個逗號分隔
##             parts = rest_text.split(',', 2)
##             
##             if len(parts) >= 2:
##                 potential_author = parts[0].strip()
##                 if potential_author and re.search(r'[a-zA-Z]', potential_author):
##                     authors = potential_author
##                 
##                 potential_title = parts[1].strip()
##                 if len(potential_title) > 10:
##                     title = potential_title
##     
##     # 提取年份
##     year_matches = re.findall(r'\b(19\d{2}|20\d{2})\b', rest_text)
##     if year_matches:
##         year = year_matches[-1]
##     
##     return {
##         'ref_number': ref_number,
##         'authors': authors,
##         'title': title if title else "Unknown",
##         'year': year
##     }
##
## def extract_ieee_reference_full(ref_text):
##     """
##     完整解析 IEEE 格式參考文獻
##     返回：格式、文獻類型、所有欄位
##     """
##     
##     # 基本欄位初始化
##     result = {
##         'format': 'IEEE',
##         'ref_number': None,
##         'source_type': 'Unknown',
##         'authors': None,
##         'title': None,
##         'journal_name': None,
##         'conference_name': None,
##         'book_title': None,
##         'volume': None,
##         'issue': None,
##         'pages': None,
##         'year': None,
##         'month': None,
##         'publisher': None,
##         'location': None,
##         'edition': None,
##         'url': None,
##         'access_date': None,
##         'doi': None,
##         'report_number': None,
##         'patent_number': None,
##         'original': ref_text
##     }
##     
##     # 提取編號
##     number_match = re.match(r'^\s*[\[【]\s*(\d+)\s*[\]】]\s*', ref_text)
##     if not number_match:
##         return result
##     
##     result['ref_number'] = number_match.group(1)
##     rest_text = ref_text[number_match.end():].strip()
##     
##     # === 1. 提取作者和標題（使用你的引號偵測邏輯） ===
##     authors = "Unknown"
##     title = None
##     
##     # 優先找引號中的標題（作者與標題分界點）
##     quote_patterns = [
##         (r'"', r'"'),
##         (r'"', r'"'),
##         (r'「', r'」'),
##         (r'“', r'”'),
##         (r'“', r'“') ,
##         (r'\'', r'\''),
##         (r'”', r'”')
##     ]
##     
##     title_found = False
##     after_title = rest_text
##     
##     for open_q, close_q in quote_patterns:
##         pattern = re.escape(open_q) + r'(.+?)' + re.escape(close_q)
##         match = re.search(pattern, rest_text)
##         
##         if match:
##             title = match.group(1).strip()
##             title = re.sub(r'[,，.。;；:：]*$', '', title).strip()
##             result['title'] = title
##             
##             # 引號前的所有內容都是作者（包含多作者）
##             before_title = rest_text[:match.start()].strip()
##             before_title = before_title.rstrip(',，. ')
##             
##             # 移除可能的 "and" 結尾
##             before_title = re.sub(r'\s+and\s*$', '', before_title, flags=re.IGNORECASE)
##             # 移除 et al. 結尾
##             before_title = re.sub(r',?\s*et\s+al\.?$', '', before_title, flags=re.IGNORECASE)
##             
##             if before_title:
##                 # 清理開頭的編號殘留
##                 before_title = re.sub(r'^\[\d+\]\s*', '', before_title)
##                 
##                 # 完整保留所有作者（用逗號分隔的多作者）
##                 if re.search(r'[a-zA-Z\u4e00-\u9fff]', before_title) and len(before_title) > 1:
##                     authors = before_title
##             
##             result['authors'] = authors
##             after_title = rest_text[match.end():].strip()
##             title_found = True
##             break
##     
##     # 如果沒有找到引號標題，用備選方案
##     if not title_found:
##         # 嘗試用 "and" 判斷作者區段結尾
##         and_match = re.search(r'\band\b', rest_text, re.IGNORECASE)
##         
##         if and_match:
##             after_and = rest_text[and_match.end():].strip()
##             next_comma = after_and.find(',')
##             
##             if next_comma > 0:
##                 # 從開頭到 "and" 後第一個逗號為作者
##                 authors_section = rest_text[:and_match.end() + next_comma].strip()
##                 authors_section = authors_section.rstrip(',，. ')
##                 
##                 # 完整保留作者區段
##                 if authors_section and re.search(r'[a-zA-Z]', authors_section):
##                     authors = authors_section
##                     result['authors'] = authors
##                 
##                 # 逗號後的內容為標題候選
##                 remaining = rest_text[and_match.end() + next_comma:].strip()
##                 remaining = remaining.lstrip(',，. ')
##                 
##                 title_match = re.match(r'^([^,，.。]+)', remaining)
##                 if title_match:
##                     potential_title = title_match.group(1).strip()
##                     if len(potential_title) > 10:
##                         title = potential_title
##                         result['title'] = title
##                 
##                 after_title = remaining
##         else:
##             # 沒有 "and"，嘗試用第一個逗號分隔
##             parts = rest_text.split(',', 2)
##             
##             if len(parts) >= 2:
##                 potential_author = parts[0].strip()
##                 if potential_author and re.search(r'[a-zA-Z]', potential_author):
##                     authors = potential_author
##                     result['authors'] = authors
##                 
##                 potential_title = parts[1].strip()
##                 if len(potential_title) > 10:
##                     title = potential_title
##                     result['title'] = title
##                 
##                 if len(parts) >= 3:
##                     after_title = parts[2]
##     
##     # === 2. 判斷文獻類型 ===
##     if re.search(r'\bin\b.*(Proc\.|Proceedings|Conference|Symposium|Workshop)', after_title, re.IGNORECASE):
##         result['source_type'] = 'Conference Paper'
##         conf_match = re.search(r'\bin\s+(.+?)(?:,|\d{4})', after_title, re.IGNORECASE)
##         if conf_match:
##             result['conference_name'] = conf_match.group(1).strip()
##     
##     elif re.search(r'(vol\.|volume|no\.|number)', after_title, re.IGNORECASE):
##         result['source_type'] = 'Journal Article'
##         journal_match = re.search(r'^([^,]+)', after_title)
##         if journal_match:
##             result['journal_name'] = journal_match.group(1).strip()
##     
##     elif re.search(r'\[Online\]|Available:|https?://', after_title, re.IGNORECASE):
##         result['source_type'] = 'Website/Online'
##
##     elif re.search(r'\[Online\]|Available:|https?://|arxiv\.org', after_title, re.IGNORECASE):
##         result['source_type'] = 'Website/Online'
##
##     elif re.search(r'(Ph\.D\.|M\.S\.|thesis|dissertation)', after_title, re.IGNORECASE):
##         result['source_type'] = 'Thesis/Dissertation'
##     
##     elif re.search(r'(Tech\. Rep\.|Technical Report)', after_title, re.IGNORECASE):
##         result['source_type'] = 'Technical Report'
##     
##     elif re.search(r'Patent', after_title, re.IGNORECASE):
##         result['source_type'] = 'Patent'
##     
##     elif re.search(r'(Ed\.|Eds\.|edition)', after_title, re.IGNORECASE):
##         result['source_type'] = 'Book'
##     
##     # === 3. 提取通用欄位 ===
##
##     # 卷號
##     vol_match = re.search(r'vol\.\s*(\d+)', after_title, re.IGNORECASE)
##     if vol_match:
##         result['volume'] = vol_match.group(1)
##
##     # 期號
##     issue_match = re.search(r'no\.\s*(\d+)', after_title, re.IGNORECASE)
##     if issue_match:
##         result['issue'] = issue_match.group(1)
##
##     # 頁碼（改進：更精確的匹配，避免抓到授權資訊中的數字）
##     pages_match = re.search(r'pp\.\s*([\d]+\s*[–\-—]\s*[\d]+)', after_title, re.IGNORECASE)
##     if pages_match:
##         # 清理頁碼中的空格
##         pages = pages_match.group(1)
##         pages = re.sub(r'\s+', '', pages)  # 移除空格
##         pages = pages.replace('–', '-').replace('—', '-')  # 統一連字符
##         result['pages'] = pages
##
##     # 年份
##     year_matches = re.findall(r'\b(19\d{2}|20\d{2})\b', after_title)
##     if year_matches:
##         result['year'] = year_matches[0]  # 取第一個年份（避免抓到下載日期）
##
##     # 月份
##     month_match = re.search(r'\b(Jan\.|Feb\.|Mar\.|Apr\.|May|Jun\.|Jul\.|Aug\.|Sep\.|Oct\.|Nov\.|Dec\.)\b', 
##                         after_title, re.IGNORECASE)
##     if month_match:
##         result['month'] = month_match.group(1)
##
##     # URL（改進：支援 arXiv、GitHub 等各種 URL，含空格處理）
##     url = None
##
##     # 1. 優先直接抓 Available: / Retrieved from 後的網址，全長且允許空白
##     url_match = re.search(r'(?:Available:|Retrieved from)\s*(https?://[^\s,]+(?:\s+[^\s,]+)*)', after_title, re.IGNORECASE)
##     if url_match:
##         # 合併所有換行與空白使其為一行
##         url = url_match.group(1).strip().replace(' ', '')
##
##     # 2. 如果沒抓到，再抓所有 http 開頭到遇到空白/逗號/句號/結尾
##     if not url:
##         generic_url_match = re.search(r'(https?://[^\s,.;]+)', after_title)
##         if generic_url_match:
##             url = generic_url_match.group(1).strip()
##
##     # 3. 最後寫入 result
##     if url:
##         result['url'] = url
##
##     # 存取日期（改進：更精確匹配）
##     access_match = re.search(
##         r'(?:accessed|retrieved|downloaded)\s+(?:on\s+)?([A-Za-z]+\.?\s+\d{1,2},?\s*\d{4})', 
##         after_title, 
##         re.IGNORECASE
##     )
##     if access_match:
##         result['access_date'] = access_match.group(1)
##
##     # DOI（新增：支援多種 DOI 格式）
##     doi_patterns = [
##         r'doi:\s*(10\.\d{4,}/[^\s,]+)',  # 標準格式：doi: 10.xxxx/xxxxx
##         r'https?://(?:dx\.)?doi\.org/(10\.\d{4,}/[^\s,]+)',  # URL 格式：https://doi.org/10.xxxx/xxxxx
##         r'DOI:\s*(10\.\d{4,}/[^\s,]+)',  # 大寫 DOI
##     ]
##
##     for pattern in doi_patterns:
##         doi_match = re.search(pattern, after_title, re.IGNORECASE)
##         if doi_match:
##             result['doi'] = doi_match.group(1).rstrip('.,;')
##             break
##
##     # 出版社與地點
##     publisher_match = re.search(
##         r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s+([A-Z]{2,}(?:,\s+[A-Z]{2,})?)\s*:\s*([^,]+)', 
##         after_title
##     )
##     if publisher_match:
##         result['location'] = publisher_match.group(1) + ', ' + publisher_match.group(2)
##         result['publisher'] = publisher_match.group(3)
##
##     # 版本
##     edition_match = re.search(r'(\d+(?:st|nd|rd|th)\s+ed\.)', after_title, re.IGNORECASE)
##     if edition_match:
##         result['edition'] = edition_match.group(1)
##
##     # 報告編號
##     report_match = re.search(r'(Tech\.\s+Rep\.|Rep\.)\s+([\w\-]+)', after_title, re.IGNORECASE)
##     if report_match:
##         result['report_number'] = report_match.group(2)
##
##     # 專利號
##     patent_match = re.search(r'(U\.S\.|US)\s+Patent\s+([\d,]+)', after_title, re.IGNORECASE)
##     if patent_match:
##         result['patent_number'] = patent_match.group(2)
##     
##     return result
##
##
##
## def extract_apa_reference_info_fixed(ref_text):
##     """
##     APA 格式擷取（修正多作者問題 + 支援完整日期 + 改進標題擷取）
##     """
##     
##     # 找年份（必須有括號,支援完整日期格式）
##     year_match = re.search(
##         r'[（(]\s*(\d{4}[a-z]?|n\.d\.)\s*(?:,\s*([A-Za-z]+\.?\s*\d{0,2}))?\s*[）)]',
##         ref_text, 
##         re.IGNORECASE
##     )
##     
##     if not year_match:
##         return {
##             'author': 'Unknown',
##             'year': 'Unknown',
##             'date': None,
##             'title': None
##         }
##     
##     year_text = year_match.group(1)
##     year = year_text[:4] if year_text.lower() != 'n.d.' else 'n.d.'
##     
##     # 提取完整日期（如果有月份日期）
##     date_str = year_match.group(2) if year_match.group(2) else None
##     
##     # 提取作者（年份前的內容）
##     before_year = ref_text[:year_match.start()].strip()
##     author = "Unknown"
##     
##     if before_year:
##         # 移除末尾的標點和空格
##         before_year = before_year.rstrip(',，. ')
##         
##         # 檢查長度和內容
##         if 2 <= len(before_year) <= 300:
##             # 排除無效的作者名
##             invalid_patterns = [
##                 r'^\d+$',  # 純數字
##                 r'^[，,\.。]+$',  # 純標點
##             ]
##             
##             is_valid = True
##             for pattern in invalid_patterns:
##                 if re.match(pattern, before_year, re.IGNORECASE):
##                     is_valid = False
##                     break
##             
##             # 直接使用整個 before_year（保留多作者）
##             if is_valid and re.search(r'[a-zA-Z\u4e00-\u9fff]', before_year):
##                 author = before_year
##     
##     # 提取標題（年份後的內容）
##     after_year = ref_text[year_match.end():].strip()
##     title = None
##     
##     if after_year:
##         # 移除開頭的標點符號和空格
##         after_year = re.sub(r'^[\s.,，。)\]】]+', '', after_year)
##         
##         if after_year:
##             # 先處理特殊情況：斜體標記
##             after_year = re.sub(r'</?i>', '', after_year)
##             
##             # 1. 先找是否有明確的標題結束標記
##             title_end_markers = [
##                 r'Retrieved from',
##                 r'Available from',
##                 r'Available at',
##                 r'\[Electronic version\]',
##                 r'DOI:',
##                 r'doi:',
##                 r'https?://',
##             ]
##             
##             title_end_pos = len(after_year)
##             for marker in title_end_markers:
##                 match = re.search(marker, after_year, re.IGNORECASE)
##                 if match and match.start() < title_end_pos:
##                     title_end_pos = match.start()
##             
##             # 取標題結束標記前的內容
##             title_candidate = after_year[:title_end_pos].strip()
##             
##             # 2. 清理標題末尾
##             # 移除末尾的期刊資訊標記
##             title_candidate = re.sub(
##                 r'\s*[\.,]\s*$',
##                 '',
##                 title_candidate
##             )
##             
##             # 移除可能的期刊名稱（斜體標記後的內容）
##             # 例如: "Title. Journal Name" -> "Title"
##             if '.' in title_candidate:
##                 parts = title_candidate.split('.')
##                 # 如果第一部分夠長,就用第一部分
##                 if len(parts[0].strip()) >= 10:
##                     title_candidate = parts[0].strip()
##             
##             # 3. 驗證標題
##             if len(title_candidate) >= 5:
##                 if not re.match(r'^(Retrieved|Available|DOI|doi|https?|www)', title_candidate, re.IGNORECASE):
##                     if not (title_candidate.isupper() and len(title_candidate) < 20):
##                         title = title_candidate
##     
##     return {
##         'author': author,
##         'year': year,
##         'date': date_str,
##         'title': title
##     }
##
## def extract_apalike_reference_info_fixed(ref_text):
##     """修正版 APA_LIKE 格式擷取"""
##     
##     years = find_apalike(ref_text)
##     
##     if not years:
##         return {
##             'author': 'Unknown',
##             'year': 'Unknown',
##             'title': None,
##             'format': 'APA_LIKE'
##         }
##     
##     year_str, year_pos = years[-1]
##     year = year_str[:4]
##     
##     before_year = ref_text[:year_pos].strip()
##     
##     author = "Unknown"
##     title = None
##     
##     parts = re.split(r'[,，.。]', before_year)
##     parts = [p.strip() for p in parts if p.strip()]
##     
##     if parts:
##         if parts[0] and re.search(r'[a-zA-Z\u4e00-\u9fff]', parts[0]):
##             author = parts[0]
##         
##         if len(parts) > 1:
##             potential_title = parts[1]
##             if potential_title and len(potential_title) > 5:
##                 title = potential_title
##     
##     return {
##         'author': author,
##         'year': year,
##         'title': title,
##         'format': 'APA_LIKE'
##     }
##
##
## def merge_ieee_references(ref_paragraphs):
##     """增強版 IEEE 段落合併"""
##     merged = []
##     current_ref = ""
##     
##     for para in ref_paragraphs:
##         para = para.strip()
##         if not para:
##             continue
##         
##         if re.match(r'^\s*[【\[]\s*\d+\s*[】\]]\s*', para):
##             if current_ref:
##                 merged.append(current_ref.strip())
##             current_ref = para
##             continue
##         
##         if len(para) < 20:
##             current_ref += " " + para
##             continue
##         
##         if re.match(r'^[a-z]', para):
##             current_ref += " " + para
##             continue
##         
##         if re.match(r'^[,，.。;；:"\'\-]', para):
##             current_ref += " " + para
##             continue
##         
##         if any(keyword in para for keyword in ['http', 'doi:', 'DOI:', '[Online]', 'Available', '.pdf', '.doi']):
##             current_ref += " " + para
##             continue
##         
##         if current_ref and not re.search(r'[.。!！?？]$', current_ref.strip()):
##             current_ref += " " + para
##             continue
##         
##         if re.match(r'^[A-Z][a-z]+(?:\s+and\s+|\s*,\s*)', para):
##             current_ref += " " + para
##             continue
##         
##         if current_ref:
##             current_ref += " " + para
##         else:
##             current_ref = para
##     
##     if current_ref:
##         merged.append(current_ref.strip())
##     
##     return merged
##
##
## def extract_reference_info(ref_paragraphs):
##     """從參考文獻段落中提取基本資訊（使用修正版）"""
##     if not ref_paragraphs:
##         return []
##     
##     first_ref = normalize_text(ref_paragraphs[0])
##     is_ieee_format = re.match(r'^\s*[【\[]\s*\d+\s*[】\]]\s*', first_ref)
##     
##     if is_ieee_format:
##         ref_paragraphs = merge_ieee_references(ref_paragraphs)
##     
##     ref_list = []
    
##     for ref_text in ref_paragraphs:
##         format_type = detect_reference_format(ref_text)
##         
##         if format_type == 'IEEE':
##             ieee_info = extract_ieee_reference_info_fixed(ref_text)
##             
##             if ieee_info:
##                 ref_list.append({
##                     'author': ieee_info['authors'],
##                     'year': ieee_info['year'],
##                     'date': None,
##                     'ref_number': ieee_info['ref_number'],
##                     'title': ieee_info['title'],
##                     'format': 'IEEE',
##                     'original': ref_text
##                 })
##             else:
##                 ref_list.append({
##                     'author': 'Parse Error',
##                     'year': 'Unknown',
##                     'date': None,
##                     'ref_number': 'Unknown',
##                     'title': None,
##                     'format': 'IEEE',
##                     'original': ref_text
##                 })
##         
##         elif format_type == 'APA':
##             apa_info = extract_apa_reference_info_fixed(ref_text)
##             ref_list.append({
##                 'author': apa_info['author'],
##                 'year': apa_info['year'],
##                 'date': apa_info.get('date'), 
##                 'ref_number': None,
##                 'title': apa_info['title'],
##                 'format': 'APA',
##                 'original': ref_text
##             })
##         
##         elif format_type == 'APA_LIKE':
##             apalike_info = extract_apalike_reference_info_fixed(ref_text)
##             ref_list.append({
##                 'author': apalike_info['author'],
##                 'year': apalike_info['year'],
##                 'date': None,
##                 'ref_number': None,
##                 'title': apalike_info['title'],
##                 'format': 'APA_LIKE',
##                 'original': ref_text
##             })
##         
##         else:
##             ref_list.append({
##                 'author': 'Unknown Format',
##                 'year': 'Unknown',
##                 'date': None,
##                 'ref_number': None,
##                 'title': None,
##                 'format': 'Unknown',
##                 'original': ref_text
##             })
##     
##     return ref_list


# ==================== [NEW] test1201 + 1204 斷行合併邏輯 (新版) ====================

def find_apa_head(ref_text):
    """[NEW] 偵測 APA 格式開頭 (年份) - 取代舊的 find_apa"""
    # 英文 APA: Author (2020).
    # 中文 APA: 作者 (2020)。
    match = re.search(r'[（(]\s*(\d{4}(?:[a-z])?|n\.d\.)\s*(?:,\s*([A-Za-z]+\.?\s*\d{0,2}))?\s*[)）]', ref_text)
    if not match: return False
    
    # 確保年份括號出現在前面 (例如前 50 個字內，避免誤判文中的年份)
    if match.start() > 80: return False 
    
    return True

def is_reference_head_unified(para):
    """
    [UPDATED] [APA/混合模式] 判斷一行文字是否為新文獻
    """
    para = normalize_text(para)

    # DOI 特徵：數字開頭 + 斜線 + 字母數字混合
    if re.match(r'^\d{4,}/[a-z0-9\.\-/]+', para, re.IGNORECASE):
        return False
    
    # 0. ✅ 強特徵白名單：明確的新文獻開頭（優先級最高）
    
    # A. 編號格式 [1]
    if re.match(r'^\s*[\[【]\s*\d+\s*[】\]]', para):
        return True
    
    # B. 標準 APA 作者格式：Last, F. 開頭
    # 只要開頭是 "姓, 名縮寫"，且不是小寫或數字開頭，就很可能是新文獻
    # 不管年份在哪（可能被斷行到下一段）
    author_start = re.match(r'^([A-Z][A-Za-z\-\']+),\s+([A-Z]\.(?:\s*[A-Z]\.)*)', para)
    if author_start:
        # 進一步驗證：排除明顯不是作者的情況
        # 1. 後面不能直接接小寫字母（表示是句子中間）
        after_author = para[author_start.end():].strip()
        if after_author and after_author[0].islower():
            pass  # 可能是句子，不處理
        else:
            # 2. 檢查是否有合理的後續內容（逗號、&、or、年份括號）
            if re.match(r'^[,&\(]', after_author) or not after_author:
                return True
            # 3. 如果後面還有其他作者名（說明是作者列表開頭）
            if re.search(r'[,&]\s+[A-Z][a-z]+,\s+[A-Z]\.', after_author[:50]):
                return True
    
    # 1. 🚫 黑名單：絕對不是新文獻的情況
    
    # A. 網址保護
    if re.search(r'(https?://|doi\.org|doi:|www\.)', para, re.IGNORECASE):
        url_only = re.sub(r'https?://[^\s]+', '', para).strip()
        if len(url_only) < 10:
            return False
        if not (re.match(r'^\s*[\[【]', para) or author_start):
            return False
            
    # B. 月份/日期保護
    if re.match(r'^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*\d{4}', para, re.IGNORECASE):
        return False
        
    # C. 卷期頁碼保護
    if re.match(r'^(Vol\.|No\.|pp\.|p\.|Page)', para, re.IGNORECASE):
        return False
        
    # D. 小寫開頭保護
    if re.match(r'^[a-z]', para):
        return False
    
    # E. 作者列表延續保護（只有 & 或逗號+名字，沒有姓氏開頭）
    # 例如：", & Varatharajan, S." 這種不算新文獻開頭
    if re.match(r'^[,&]\s', para):
        return False

    # 如果開頭是縮寫（如 "A., Malhotra"），但後面沒有年份括號 (20XX)
    # 這是作者列表延續，不是新文獻開頭
    # 例如："A., Malhotra, R. K., & Martin, J. L." (沒有年份)
    if re.match(r'^[A-Z]\.(?:\s*[A-Z]\.)*\s*,', para):
        # 檢查這一段是否有年份括號 (19XX) 或 (20XX)
        # 如果沒有年份，這肯定是作者列表延續
        if not re.search(r'[（(]\s*(?:19|20)\d{2}', para):
            return False

    # 2. ✅ 其他白名單特徵
    
    # C. APA 標準格式 (Year) - 年份在括號內
    if find_apa_head(para):
        return True
        
    # D. 類 APA (Year in dots)
    year_match = re.search(r'[\.,]\s*(19|20)\d{2}[a-z]?[\.,]', para[:80])
    if year_match:
        pre_text = para[:year_match.start()].strip()
        if len(pre_text) > 3:
            if not has_chinese(para):
                if ',' in pre_text or '.' in pre_text:
                    return True
            else:
                return True

    return False

def merge_references_unified(paragraphs):
    """[UPDATED from test1204-6] [APA/混合模式] 合併斷行"""
    merged = []
    current_ref = ""
    
    for i, para in enumerate(paragraphs):
        para = para.strip()
        if not para: continue
        
        # 排除純數字頁碼 (長度短且無連字號)
        if para.isdigit() and len(para) < 4: continue

        # 排除頁首/頁尾文字
        # 特徵：全大寫、長度短、沒有年份括號、沒有編號
        if para.isupper() and len(para) < 50:
            # 1. 包含 ET AL 的作者頁首
            if 'ET AL' in para:
                continue
            # 2. 縮寫開頭的頁首（如 "S. JAYDARIFARD ET AL."）
            if re.match(r'^[A-Z]\.\s+[A-Z]+', para):
                continue
            # 3. 期刊名稱或章節標題的頁首（如 "TRANSPORT REVIEWS"）
            # 排除條件：全大寫 + 沒有數字 + 沒有括號 + 沒有標點（除了空格）
            if not re.search(r'[\d\(\)\[\]\.,:;]', para):
                continue  # 跳過這行
        
        is_new_ref = is_reference_head_unified(para)

        # 特殊判斷：如果當前文獻以 & 或 , 結尾（表示作者列表未完成）
        # 且這行開頭是作者名+年份，這行應該是作者列表的最後一位，不是新文獻
        if is_new_ref and current_ref:
            # 檢查上一行結尾
            current_ref_stripped = current_ref.rstrip()
            if current_ref_stripped.endswith('&') or current_ref_stripped.endswith(','):
                # 檢查這行是否為：作者名 + 年份（作者列表最後一位的模式）
                # 例如：Varatharajan, S. (2019). ...
                if re.match(r'^[A-Z][A-Za-z\-\']+,\s+[A-Z]\.\s*[（(]', para):
                    # 這是作者列表的最後一位，應該合併
                    is_new_ref = False

        # 如果當前累積的文獻沒有年份，且新段落有年份
        # 那新段落應該是當前文獻的延續，不是新文獻
        if is_new_ref and current_ref:
            # 檢查 current_ref 是否有年份
            has_year_in_current = bool(re.search(r'[（(]\s*(?:19|20)\d{2}', current_ref))
            # 檢查 para 是否有年份
            has_year_in_para = bool(re.search(r'[（(]\s*(?:19|20)\d{2}', para))
            
            # 如果當前文獻沒年份，但新段落有年份 → 新段落是延續
            if not has_year_in_current and has_year_in_para:
                is_new_ref = False
        
        if is_new_ref:
            if current_ref:
                merged.append(current_ref)
            current_ref = para
        else:
            if current_ref:
                if has_chinese(current_ref[-1:]) and has_chinese(para[:1]):
                    current_ref += "" + para
                elif current_ref.endswith('-'):
                    # 判斷是否為單字斷行
                    if para and para[0].islower():
                        current_ref = current_ref[:-1] + para
                    else:
                        current_ref = current_ref + " " + para
                # 處理頁碼斷行：連字號+空格+數字
                elif re.search(r'[\–\-—]\s*$', current_ref) and para and para[0].isdigit():
                    current_ref = current_ref.rstrip() + para
                # 處理 DOI 斷行
                elif re.search(r'doi\.org/[^\s]+\.$', current_ref, re.IGNORECASE) and para and para[0].isdigit():
                    current_ref = current_ref + para  # DOI 直接連接
                # 處理一般 URL 結尾是句點的斷行
                elif re.search(r'https?://[^\s]+\.$', current_ref) and para and not para[0].isupper():
                    current_ref = current_ref + para
                else:
                    current_ref += " " + para
            else:
                current_ref = para
            
    if current_ref: 
        merged.append(current_ref)
    
    return merged

def merge_references_ieee_strict(paragraphs):
    """
    [NEW from test1204-6] [IEEE 專用模式] 嚴格合併
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
                # 萬一第一行就沒抓到編號，先當作第一條
                current_ref = para
                
    if current_ref: merged.append(current_ref)
    return merged


# ==================== [NEW] test1201 詳細解析引擎 (已啟用) ====================

# --- 英文解析 ---
def parse_apa_authors_en(author_str):
    if not author_str: return []
    
    # 先處理 & 或 and（APA 最後一個作者前的連接詞）
    # 將 & 或 and 替換成逗號，統一處理
    clean_str = re.sub(r'\s*,?\s*(&|and)\s+', ', ', author_str, flags=re.IGNORECASE)
    
    # 用「., 」（點號+逗號+空格）來分割作者
    # 這樣可以正確處理 "Last, F. M., Next, A."
    segments = re.split(r'\.\s*,\s*', clean_str)
    
    authors = []
    for seg in segments:
        seg = seg.strip()
        if not seg: continue
        
        # 移除結尾的點號（如果有）
        seg = seg.rstrip('.')
        
        if ',' in seg:
            # 格式：Last, F. M.
            parts = seg.split(',', 1)
            last = parts[0].strip()
            first = parts[1].strip()
            # 確保 first name 有點號結尾
            if first and not first.endswith('.'):
                first += '.'
            authors.append({'last': last, 'first': first})
        else:
            # 只有姓氏
            authors.append({'last': seg, 'first': ''})
    
    return authors

def extract_apa_en_detailed(ref_text):
    result = {
        'format': 'APA (EN)', 'lang': 'EN',
        'authors': "Unknown", 'parsed_authors': [],
        'year': None, 'title': None, 'source': None,
        'volume': None, 'issue': None, 'pages': None,
        'article_number': None,
        'publisher': None,
        'editors': None,
        'book_title': None,
        'source_type': None,  
        'url': None,
        'doi': None, 'original': ref_text
    }

    # 先提取 DOI 和 URL (提前處理，避免干擾標題解析)
    result['doi'] = extract_doi(ref_text)

    # 提取 URL (支援各種格式，包含空格斷行和連字號斷行)
    # 找到 https:// 開頭，然後向後抓取直到遇到明確的結束標記
    url_start = re.search(r'https?://', ref_text)
    if url_start:
        # 從 https:// 開始向後掃描
        start_pos = url_start.start()
        url_text = ref_text[start_pos:]
        
        # 找到 URL 結束的位置（遇到句號+空格、逗號、或文末）
        # 但要允許 URL 內部的點、斜線、連字號、空格
        end_match = re.search(r'(?:\.\s+[A-Z]|,\s|$)', url_text)
        if end_match:
            raw_url = url_text[:end_match.start()].strip()
        else:
            raw_url = url_text.strip()
        
        # 清理 URL：
        # 1. 先處理「連字號+空白」-> 保留連字號
        clean_url = re.sub(r'-\s+', '-', raw_url)
        # 2. 移除所有剩餘空白
        clean_url = re.sub(r'\s+', '', clean_url)
        # 3. 移除結尾的句號（如果有）
        clean_url = clean_url.rstrip('.')
        
        result['url'] = clean_url
        # 保留 url_match 供後續使用
        url_match = type('obj', (object,), {'group': lambda self, n: raw_url if n == 0 else None})()
    else:
        url_match = None
    
    year_match = re.search(r'[（(]\s*(\d{4}[a-z]?|n\.d\.)\s*(?:,\s*[A-Za-z]+\.?\s*\d{0,2})?\s*[)）]', ref_text)
    if not year_match: return result
    
    year_group = year_match.group(1)
    result['year'] = year_group if year_group.lower() != 'n.d.' else 'n.d.'

    # 提取完整日期 (Month Day) - 先檢查 group 是否存在
    try:
        date_match = year_match.group(2)
        if date_match:
            result['month'] = date_match
    except IndexError:
        pass  # 沒有月份資訊，跳過
    
    author_part = ref_text[:year_match.start()].strip()
    result['authors'] = author_part
    result['parsed_authors'] = parse_apa_authors_en(author_part)
    
    content_part = ref_text[year_match.end():].strip()
    if content_part.startswith('.'): content_part = content_part[1:].strip()

    # 移除 DOI 和 URL，避免它們被誤判為標題或來源
    if result['doi']:
        content_part = re.sub(r'(?:doi:|DOI:|https?://doi\.org/)\s*10\.\d{4,}/[^\s。]+', '', content_part).strip()

    if result['url']:
        # 移除原始 URL（包含所有可能的空格變體）
        if url_match:
            # 將原始 URL 中的空格變成彈性匹配模式
            original_url_text = url_match.group(0)
            # 將 URL 拆成片段，用 \s* 連接（允許任意空格）
            url_parts = original_url_text.split()
            flexible_pattern = r'\s*'.join(re.escape(part) for part in url_parts)
            content_part = re.sub(flexible_pattern, '', content_part, flags=re.IGNORECASE)
        
        # 也移除清理後的 URL（以防萬一）
        content_part = content_part.replace(result['url'], '')
        
        # 清理殘留的多餘空格和標點
        content_part = re.sub(r'\s+', ' ', content_part).strip()
        content_part = content_part.rstrip('. ')

    # 判斷是否為書籍章節或一般書籍
    # 優先檢查是否為書籍章節格式（In ... (Eds.)）
    is_book_chapter = bool(re.search(r'\bIn\s+.+?\s*\(Eds?\.\)', content_part, re.IGNORECASE))
    # 或是作者為編者，或標題包含書籍關鍵字
    is_book = is_book_chapter or bool(
        re.search(r'\(eds?\.\)', author_part, re.IGNORECASE) or 
        re.search(r'\b(manual|handbook|guide|textbook|encyclopedia|dictionary)\b', content_part, re.IGNORECASE)
    )

    # 提取後設資料 (卷期頁碼/文章編號)
    # 格式 1: Journal, Vol(Issue), pages. 例如：Journal, 14(2), 123-456.
    meta_match = re.search(r',\s*(\d+)(?:\s*\((\d+)\))?,\s*([\d\–\-]+)(?:\.|\s|$)', content_part)

    if meta_match:
        result['volume'] = meta_match.group(1)
        result['issue'] = meta_match.group(2)
        pages_or_article = meta_match.group(3)
        
        # 判斷是頁碼還是文章編號
        # 文章編號通常是純數字（如 100571），頁碼有連字號（如 123-456）
        if '-' in pages_or_article or '–' in pages_or_article:
            result['pages'] = pages_or_article
        else:
            # 純數字，可能是文章編號
            if len(pages_or_article) >= 5:  # 文章編號通常較長
                result['article_number'] = pages_or_article
            else:
                result['pages'] = pages_or_article  # 短數字可能還是頁碼
        
        title_source_part = content_part[:meta_match.start()].strip()

    else:
        # 格式 2: 傳統頁碼格式 pp. 123-456
        pp_match = re.search(r',?\s*pp?\.?\s*([\d\–\-]+)(?:\.)?$', content_part)
        if pp_match:
            result['pages'] = pp_match.group(1)
            title_source_part = content_part[:pp_match.start()].strip()
        else:
            title_source_part = content_part

    # 改進標題與來源分割邏輯
    if is_book:
        # === 先檢查是否為書籍章節格式 ===
        # 格式：章節標題. In 編者 (Eds.), 書名 (pp. xxx). 出版社.
        # 改進正則表達式，更精確匹配
        chapter_match = re.search(
            r'^(.+?)\.\s+In\s+(.+?)\s*\(Eds?\.\),\s*(.+?)\s*\(pp\.\s*([\d\s\–\-—]+)\)', 
            title_source_part, 
            re.IGNORECASE
        )

        if chapter_match:
            # 這是書籍章節
            result['title'] = chapter_match.group(1).strip()  # 章節標題
            result['editors'] = "In " + chapter_match.group(2).strip() + " (Eds.)"  # 編者
            result['book_title'] = chapter_match.group(3).strip()  # 書名
            
            # 清理頁碼中的多餘空格
            raw_pages = chapter_match.group(4).strip()
            clean_pages = re.sub(r'\s+', '', raw_pages)  # 移除所有空格
            result['pages'] = clean_pages  # 例如 "254–257"
            
            # 出版社在括號後面
            after_chapter = title_source_part[chapter_match.end():].strip()
            # 移除開頭的句點和空格
            after_chapter = after_chapter.lstrip('. ').strip()
            if after_chapter:
                # 移除結尾的句點
                result['publisher'] = after_chapter.rstrip('.')
            
            result['source_type'] = 'Book Chapter'
        else:
            # 一般書籍格式：標題. 出版社.
            split_match = re.search(r'\.\s+([A-Z])', title_source_part)
            
            if split_match:
                split_pos = split_match.start()
                result['title'] = title_source_part[:split_pos].strip()
                
                # 出版社部分
                publisher_part = title_source_part[split_pos + 1:].strip()
                next_dot = publisher_part.find('.')
                if next_dot != -1:
                    result['publisher'] = publisher_part[:next_dot].strip()
                else:
                    result['publisher'] = publisher_part.rstrip('.')
            else:
                result['title'] = title_source_part.rstrip('.')
    else:
        # 期刊格式：標題. 期刊名
        split_index = title_source_part.rfind('. ')
        if split_index != -1:
            result['title'] = title_source_part[:split_index].strip()
            result['source'] = title_source_part[split_index + 1:].strip().rstrip('.')
        else:
            if not title_source_part.startswith('http'):
                result['title'] = title_source_part.rstrip('.')

    # 清理所有文字欄位中的斷行連字號
    text_fields = ['title', 'source', 'publisher', 'editors', 'book_title', 'journal_name', 'conference_name']
    for field in text_fields:
        if result.get(field) and isinstance(result[field], str):
            # 移除單字中的斷行連字號（如 "perform- ance" -> "performance"）
            # 模式1: 連字號+空格+小寫字母
            result[field] = re.sub(r'-\s+([a-z])', r'\1', result[field])
            # 模式2: 單純的連字號+空格（備用）
            result[field] = re.sub(r'-\s+', '', result[field])

    return result

def parse_ieee_authors(authors_str):
    """
    [Fixed] 解析 IEEE 作者字串，強力修復 'and' 殘留問題
    Input: "D. Yang, J. Gavigan, and Z. Wilcox-O’Hearn"
    Output: [{'first': 'D.', 'last': 'Yang'}, {'first': 'Z.', 'last': "Wilcox-O’Hearn"}]
    """
    
    if not authors_str:
        return []

    # 1. 預處理：將 " and " 替換為逗號，避免混淆名字解析
    # 使用 re.IGNORECASE 確保 'And' 或 'AND' 都能被抓到
    clean_str = re.sub(r',?\s+\b(and|&)\b\s+', ',', authors_str, flags=re.IGNORECASE)
    
    # 2. 根據逗號分割作者
    # 移除多餘空白
    raw_authors = [a.strip() for a in clean_str.split(',') if a.strip()]
    
    parsed_list = []
    
    for auth in raw_authors:
        # 處理 "Last, First" 格式 (有些 IEEE 變體)
        if ',' in auth:
            parts = auth.split(',', 1)
            parsed_list.append({
                'last': parts[0].strip(),
                'first': parts[1].strip()
            })
            continue
            
        # 處理標準 "First M. Last" 格式
        # 以空格分割
        parts = auth.split()
        if not parts:
            continue
            
        if len(parts) == 1:
            # 只有一個字，假定為 Last Name
            parsed_list.append({'first': '', 'last': parts[0]})
        else:
            # 最後一個部分當作 Last Name
            # 前面所有部分當作 First Name (包含 Middle Name)
            last_name = parts[-1]
            first_name = " ".join(parts[:-1])
            
            # [特例處理]：如果名字裡還有殘留的 'and' (極端情況)，再清一次
            first_name = re.sub(r'\band\b', '', first_name, flags=re.IGNORECASE).strip()
            
            parsed_list.append({
                'first': first_name,
                'last': last_name
            })
            
    return parsed_list


def extract_ieee_reference_full(ref_text):
    """
    [Final Fixed Version] 完整解析 IEEE 格式參考文獻
    包含針對 Ethereum, arXiv, BitTicket, DOI重複, 頁碼to, 年份誤刪, 月份誤判, Downloaded清理 等所有案例的修復。
    """
    
    # 基本欄位初始化
    result = {
        'format': 'IEEE',
        'ref_number': None,
        'source_type': 'Unknown',
        'authors': None,
        'parsed_authors': [],
        'title': None,
        'source': None,
        'journal_name': None,
        'conference_name': None,
        'volume': None,
        'issue': None,
        'pages': None,
        'year': None,
        'month': None,
        'publisher': None,
        'location': None,
        'edition': None,
        'url': None,
        'access_date': None,
        'doi': None,
        'report_number': None,
        'patent_number': None,
        'original': ref_text
    }
    
    # 1. 提取編號 [1]
    number_match = re.match(r'^\s*[\[【]\s*(\d+)\s*[\]】]\s*', ref_text)
    if not number_match: return result 
    
    result['ref_number'] = number_match.group(1)
    rest_text = ref_text[number_match.end():].strip()
    
    # === 2. 提取作者和標題 ===
    quote_patterns = [
        (r'"', r'"'), (r'“', r'”'), (r'“', r'“'),  (r'”', r'”'),(r'\'', r'\''), (r'「', r'」')
    ]
    
    title_found = False
    after_title = rest_text 
    
    for open_q, close_q in quote_patterns:
        pattern = re.escape(open_q) + r'(.+?)' + re.escape(close_q)
        match = re.search(pattern, rest_text)
        if match:
            # 抓到標題
            title = match.group(1).strip().rstrip(',.。;；:：')
            result['title'] = title
            # 抓到作者
            before_title = rest_text[:match.start()].strip().rstrip(',. ')
            before_title = re.sub(r'\s+and\s*$', '', before_title, flags=re.IGNORECASE)
            before_title = re.sub(r',?\s*et\s+al\.?$', '', before_title, flags=re.IGNORECASE)
            if before_title:
                result['authors'] = before_title
                if 'parse_ieee_authors' in globals():
                    result['parsed_authors'] = parse_ieee_authors(before_title)
            
            after_title = rest_text[match.end():].strip()
            title_found = True
            break
            
    # Fallback: 沒引號，啟動智慧救援
    if not title_found:
        year_split_match = re.search(r'(?:,|^)\s*(\d{4}[a-z]?)(?:\.|,)\s*', rest_text)
        if year_split_match:
            authors_candidate = rest_text[:year_split_match.start()].strip().strip(',. ')
            title_candidate = rest_text[year_split_match.end():].strip()
            result['year'] = year_split_match.group(1)

            # 檢查作者欄位是否誤含 URL
            url_in_author = re.search(r'(?:,|^|\s)(URL|Available|http)', authors_candidate, re.IGNORECASE)
            if url_in_author:
                after_title = authors_candidate[url_in_author.start():].strip()
                real_content = authors_candidate[:url_in_author.start()].strip().strip(',. ')
                dot_split = re.search(r'\.\s+', real_content)
                if dot_split:
                    result['authors'] = real_content[:dot_split.start() + 1].strip()
                    result['title'] = real_content[dot_split.end():].strip()
                else:
                    result['authors'] = real_content
            else:
                result['authors'] = authors_candidate
                in_split_match = re.search(r'(?:\.|,|\s)\s*(?:In|in):\s*', title_candidate)
                if in_split_match:
                    result['title'] = title_candidate[:in_split_match.start()].strip().rstrip('.')
                    after_title = title_candidate[in_split_match.end():].strip()
                else:
                    dot_split_match = re.search(r'\.\s+', title_candidate)
                    if dot_split_match:
                        result['title'] = title_candidate[:dot_split_match.start()].strip()
                        after_title = title_candidate[dot_split_match.end():].strip()
                    else:
                        result['title'] = title_candidate
                        after_title = title_candidate
        else:
            parts = rest_text.split(',', 1)
            if len(parts) > 1:
                result['authors'] = parts[0].strip()
                result['title'] = parts[1].strip()
                after_title = result['title']

    # 特殊修復: Ethereum foundation 等無作者情況
    if not result.get('authors') and result.get('title'):
        eth_split = re.search(r'(Ethereum foundation)\.\s*(.*)', result['title'], re.IGNORECASE)
        author_split = re.search(r'\.\s+([A-Z])', result['title'])
        if eth_split:
             result['authors'] = eth_split.group(1).strip()
             result['title'] = eth_split.group(2).strip()
        elif author_split:
             result['authors'] = result['title'][:author_split.start()].strip()
             result['title'] = result['title'][author_split.start() + 1:].strip()

    # === [修正] 全局清理：移除資料庫授權聲明與下載資訊 ===
    after_title = re.sub(r'Authorized licensed use[\s\S]*', '', after_title, flags=re.IGNORECASE)
    after_title = re.sub(r'Downloaded\s+on[\s\S]*', '', after_title, flags=re.IGNORECASE)
    after_title = re.sub(r'IEEE Xplore[\s\S]*', '', after_title, flags=re.IGNORECASE).strip()

    # === [關鍵修復] 如果 Source 開頭是年份，且後面接標點 (如 "2019, - 4th"), 移除 ===
    # 若後面只有空格 (如 "2019 34th"), 則保留
    if not result['year']:
        # 先暫時清理干擾項以抓取準確年份
        temp_text = re.sub(r'doi:.*', '', after_title, flags=re.IGNORECASE)
        temp_text = re.sub(r'©\s*\d{4}', '', temp_text)
        # 排除 arXiv 編號中的年份 (如 2001.xxxxx)
        year_matches = re.findall(r'(?<!:)(?<!arXiv:)\b(19\d{2}|20\d{2})\b(?!\.\d)', temp_text)
        if year_matches: 
            result['year'] = year_matches[-1]
    if result['year']:
        # [修正] 加入點號 \. 到允許的分隔符列表中
        year_start_match = re.match(r'^\s*(?:[\.,]\s*)?[\(]?\s*(\d{4})\s*[\)]?[\.,]?\s*', after_title)
        if year_start_match and year_start_match.group(1) == result['year']:
            after_title = after_title[year_start_match.end():].strip()

    # === 3. 提取來源資訊 ===
    full_search_text = after_title # 經過清理後的乾淨文本
    
    # Vol
    vol_match = re.search(r'\b(?:Vol\.?|Volume)\s*(\d+)', full_search_text, re.IGNORECASE)
    if vol_match: result['volume'] = vol_match.group(1)
    
    # No (排除 Page No.)
    no_match = re.search(r'\b(?<!Page\s)no\.?\s*(\d+)', full_search_text, re.IGNORECASE)
    if no_match: result['issue'] = no_match.group(1)
    
    # Pages (支援 pp, Page No., Page)
    pp_match = re.search(r'\b(?:pp?\.?|Pages?|Page\s*No\.?)\s*(\d+(?:\s*(?:[\–\-—]|to)\s*\d+)?)', full_search_text, re.IGNORECASE)
    if pp_match: 
        raw_pages = pp_match.group(1)
        result['pages'] = re.sub(r'\s+', '', raw_pages).replace('to', '-').replace('–', '-').replace('—', '-')

    # 年份 (補抓)
    if not result['year']:
        clean_year_text = re.sub(r'doi:.*', '', full_search_text, flags=re.IGNORECASE)
        clean_year_text = re.sub(r'©\s*\d{4}', '', clean_year_text)
        year_matches = re.findall(r'(?<!:)(?<!arXiv:)\b(19\d{2}|20\d{2})\b(?!\.\d)', clean_year_text)
        if year_matches: result['year'] = year_matches[-1]

    # Source Name 截斷
    months_regex = r'\b(?:Jan\.|Jan|January|Feb\.|Feb|February|Mar\.|Mar|March|Apr\.|Apr|April|May\.?|May|Jun\.|Jun|June|Jul\.|Jul|July|Aug\.|Aug|August|Sep\.|Sep|Sept\.|September|Oct\.|Oct|October|Nov\.|Nov|November|Dec\.|Dec|December)\b'
    end_indicators = [
        r'\b(?:Vol\.?|Volume)\s*\d+',      
        r'\bno\.?\s*\d+', 
        r'\b(?:pp?\.?|Pages?|Page)\s*\d+', # [修正] 強制 Page 後面要有數字，避免誤切
        r'(?<!:)\b19\d{2}\b', 
        r'(?<!:)\b20\d{2}\b', 
        r'doi:', 
        months_regex
    ]
    min_pos = len(full_search_text)
    
    for ind in end_indicators:
        matches = list(re.finditer(ind, full_search_text, re.IGNORECASE))
        for m in matches:
            # 保護機制: 略過開頭的年份或會議關鍵字後面的年份
            if (r'19\d{2}' in ind or r'20\d{2}' in ind):
                context_after = full_search_text[m.end():]
                if m.start() < 5 and re.search(r'[a-zA-Z]', context_after): continue 
            # [修正] 加入 Lecture Notes, Proceedings 等保護關鍵字
                if re.search(r'\b(Conference|Symposium|Workshop|Congress|Meeting|Lecture Notes|Proceedings)\b',     full_search_text[m.end():m.end()+60], re.IGNORECASE):
                    continue
            if m.start() < min_pos:
                min_pos = m.start()
                break
    
    source_candidate = full_search_text[:min_pos].strip().strip(',. -')
    # 清理 Source
    clean_source = re.sub(r'^in(?:[:\s]+|$)', '', source_candidate, flags=re.IGNORECASE)
    clean_source = re.sub(r'^J\.\s+', '', clean_source)
    clean_source = re.sub(r'(?:Retrieved from|Available:|http).*', '', clean_source, flags=re.IGNORECASE)
    # [新增] 移除 [Online] 標記
    clean_source = re.sub(r'\[Online\]\.?', '', clean_source, flags=re.IGNORECASE).strip().strip(',. -')
    
    result['source'] = clean_source

    # === 4. Source Type & Details ===
    if re.search(r'(Proc\.|Proceedings|Conference|Symposium|Workshop)', full_search_text, re.IGNORECASE):
        result['source_type'] = 'Conference Paper'
        result['conference_name'] = clean_source
    elif re.search(r'(vol\.|volume|no\.|number)', full_search_text, re.IGNORECASE) and not result['conference_name']:
        result['source_type'] = 'Journal Article'
        result['journal_name'] = clean_source
    elif re.search(r'(Ph\.D\.|M\.S\.|thesis)', full_search_text, re.IGNORECASE):
        result['source_type'] = 'Thesis/Dissertation'
    elif re.search(r'(Tech\. Rep\.|Technical Report)', full_search_text, re.IGNORECASE):
        result['source_type'] = 'Technical Report'
        rep_match = re.search(r'(Tech\.\s+Rep\.|Rep\.)\s+([\w\-]+)', full_search_text, re.IGNORECASE)
        if rep_match: result['report_number'] = rep_match.group(2)
    elif re.search(r'Patent', full_search_text, re.IGNORECASE):
        result['source_type'] = 'Patent'
    elif re.search(r'\[Online\]|Available:|https?://|arxiv\.org', full_search_text, re.IGNORECASE):
        result['source_type'] = 'Website/Online'
    elif re.search(r'(Ed\.|Eds\.|edition)', full_search_text, re.IGNORECASE):
        result['source_type'] = 'Book'

    # === [關鍵修復] 月份提取 (優先匹配複合月份) ===
    months_list = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Sept", "Oct", "Nov", "Dec", 
                   "January", "February", "March", "April", "June", "July", "August", "September", "October", "November", "December"]
    month_part = r'(?:' + '|'.join(months_list) + r')\.?'
    # 複合月份 (Month-Month)
    comp_month_match = re.search(r'\b' + month_part + r'\s*[-/–]\s*' + month_part + r'\b', full_search_text, re.IGNORECASE)
    if comp_month_match:
        result['month'] = comp_month_match.group(0)
    else:
        month_match = re.search(months_regex, full_search_text, re.IGNORECASE)
        if month_match: result['month'] = month_match.group(0)
    
    # DOI
    doi_match = re.search(r'(?:doi:|DOI:|https?://doi\.org/)\s*(10\.\d{4,}/[^\s,;\]\)]+)', full_search_text)
    if doi_match: result['doi'] = doi_match.group(1).rstrip('.')
    
    # === [關鍵修復] URL 提取 (支援空格合併) ===
    # 策略 1: 針對 .pdf 結尾的連結，允許中間有空格
    pdf_url_match = re.search(r'(?:Available:|Retrieved from|URL)\s*(https?://.*?\.pdf)', full_search_text, re.IGNORECASE)
    if pdf_url_match:
        result['url'] = pdf_url_match.group(1).replace(' ', '').strip()
    else:
        # 策略 2: 標準提取
        url_match = re.search(r'(?:Available:|Retrieved from|URL)\s*(https?://[^,\n\s\]\)]+)', full_search_text, re.IGNORECASE)
        if url_match:
            result['url'] = url_match.group(1).strip()
        elif not result['url']:
            gen_url = re.search(r'(https?://[^\s,;]+(?:\.pdf)?)', full_search_text, re.IGNORECASE)
            if gen_url: result['url'] = gen_url.group(1).strip()

    if result['url'] and 'doi.org' in result['url'] and result['doi']: result['url'] = None
    if result['source'] and re.fullmatch(r'(URL|Available|Online|Retrieved|Website)', result['source'], re.IGNORECASE): result['source'] = None
    
    # Access Date
    acc_match = re.search(r'(?:accessed|retrieved|downloaded)\s+(?:on\s+)?([A-Za-z]+\.?\s+\d{1,2},?\s*\d{4})', full_search_text, re.IGNORECASE)
    if acc_match: result['access_date'] = acc_match.group(1)

    return result
# --- 中文解析 ---
def parse_chinese_authors(author_str):
    if not author_str: return []
    clean_str = re.sub(r'\s*(等|著|編)$', '', author_str)
    return re.split(r'[、，,]', clean_str)

def extract_apa_zh_detailed(ref_text):
    result = {
        'format': 'APA (ZH)', 'lang': 'ZH',
        'authors': [], 'year': None, 'title': None, 'source': None,
        'volume': None, 'issue': None, 'pages': None,
        'doi': None, 'original': ref_text
    }
    result['doi'] = extract_doi(ref_text)
    year_match = re.search(r'[（(]\s*(\d{2,4})\s*[)）]', ref_text)
    if not year_match: return result
    
    result['year'] = year_match.group(1)
    author_part = ref_text[:year_match.start()].strip()
    result['authors'] = parse_chinese_authors(author_part)
    
    rest = ref_text[year_match.end():].strip().lstrip('.。 ')
    match_book = re.search(r'《([^》]+)》', rest)
    match_article = re.search(r'〈([^〉]+)〉', rest)
    
    if match_article:
        result['title'] = match_article.group(1)
        if match_book: result['source'] = match_book.group(1)
    elif match_book:
        pre_book = rest[:match_book.start()].strip()
        if pre_book:
            result['title'] = pre_book.rstrip('。. ')
            result['source'] = match_book.group(1)
        else:
            result['title'] = match_book.group(1)
    else:
        # [UPDATED] 增加後備方案，如果沒有書名號，嘗試用句號分隔抓取來源
        parts = re.split(r'[。.]', rest)
        # 過濾空字串
        parts = [p.strip() for p in parts if p.strip()]
        if len(parts) > 0: result['title'] = parts[0]
        if len(parts) > 1: result['source'] = parts[1] # 嘗試抓取來源
            
    vol_match = re.search(r'(\d+)\s*[卷]', rest)
    if vol_match: result['volume'] = vol_match.group(1)
    return result

def extract_numbered_zh_detailed(ref_text):
    result = {
        'format': 'Numbered (ZH)', 'lang': 'ZH',
        'ref_number': None, 'authors': [], 'year': None, 'title': None, 'source': None,
        'doi': None, 'original': ref_text
    }
    result['doi'] = extract_doi(ref_text)
    num_match = re.match(r'^\s*[\[【]\s*(\d+)\s*[\]】]', ref_text)
    if num_match:
        result['ref_number'] = num_match.group(1)
        rest = ref_text[num_match.end():].strip()
    else:
        rest = ref_text
    year_match = re.search(r'\b(\d{4})\b', rest)
    if year_match: result['year'] = year_match.group(1)
    
    match_book = re.search(r'《([^》]+)》', rest)
    if match_book:
        result['source'] = match_book.group(1)
        pre = rest[:match_book.start()]
        # 嘗試抓作者和篇名
        parts = re.split(r'[，,]', pre)
        if len(parts) > 0: result['authors'] = parse_chinese_authors(parts[0])
        if len(parts) > 1: result['title'] = parts[1]
    else:
        # [UPDATED] 增加後備方案，嘗試抓取來源 (假設結構: 作者, 篇名, 來源)
        parts = re.split(r'[，,。.]', rest)
        parts = [p.strip() for p in parts if p.strip()]
        if len(parts) > 0: result['authors'] = parse_chinese_authors(parts[0])
        if len(parts) > 1: result['title'] = parts[1]
        if len(parts) > 2: result['source'] = parts[2] # 嘗試抓取來源

    return result

# --- 核心整合分流 ---
def process_single_reference(ref_text):
    """[NEW] 核心分流邏輯，根據語言和特徵選擇解析器"""
    ref_text = normalize_text(ref_text)
    
    if has_chinese(ref_text):
        if re.match(r'^\s*[\[【]', ref_text):
            data = extract_numbered_zh_detailed(ref_text)
        else:
            data = extract_apa_zh_detailed(ref_text)
    else:
        if re.match(r'^\s*[\[【]', ref_text):
            data = extract_ieee_reference_full(ref_text)
        else:
            data = extract_apa_en_detailed(ref_text)
            
    # [關鍵整合]：確保回傳的字典包含 1204 比對邏輯所需的 'author' (字串) 欄位
    if isinstance(data.get('authors'), list):
        # 這裡主要是為了比對邏輯，前端顯示會有專門的處理
        data['author'] = " ".join(data['authors']) 
    elif isinstance(data.get('authors'), str):
        data['author'] = data['authors']
    else:
        data['author'] = "Unknown"
        
    return data

# ==================== [NEW] test1201 格式轉換功能 ====================

def convert_en_apa_to_ieee(data):
    ieee_authors = []
    for auth in data.get('parsed_authors', []):
        ieee_authors.append(f"{auth['first']} {auth['last']}".strip())
    auth_str = ", ".join(ieee_authors)
    if len(ieee_authors) > 2: auth_str = re.sub(r', ([^,]+)$', r', and \1', auth_str)
    
    parts = []
    if auth_str: parts.append(auth_str + ",")
    if data.get('title'): parts.append(f'"{data["title"]},"')
    
    # 分別處理期刊和書籍
    if data.get('source'):  # 期刊
        parts.append(f"{data['source']},")
    elif data.get('publisher'):  # 書籍
        parts.append(f"{data['publisher']},")
    
    if data.get('volume'): parts.append(f"vol. {data['volume']},")
    if data.get('issue'): parts.append(f"no. {data['issue']},")
    if data.get('pages'): parts.append(f"pp. {data['pages']},")
    
    # 加入月份
    if data.get('month'): parts.append(f"{data['month']}")
    if data.get('year'): parts.append(f"{data['year']}.")
    
    # 加入 DOI 或 URL
    if data.get('doi'): parts.append(f"doi: {data['doi']}.")
    elif data.get('url'): parts.append(f"[Online]. Available: {data['url']}")
    
    return " ".join(parts)

def convert_en_ieee_to_apa(data):
    """
    將解析後的 IEEE 資料轉換為標準 APA 7 格式
    修復重點：
    1. 作者連接詞 (&) 邏輯改用列表處理，避免正則誤判。
    2. 增加卷號 (Volume) 斜體、期號 (Issue) 正體、頁碼的標準格式處理。
    3. 確保每個區塊結尾都有正確的句號。
    """
    
    # === 1. 作者 (Authors) ===
    # 格式: Last, F. M., & Last, F. M.
    apa_authors = []
    parsed = data.get('parsed_authors', [])
    
    # 如果有解析好的作者資料
    if parsed:
        for auth in parsed:
            last = auth.get('last', '').strip()
            first = auth.get('first', '').strip()
            # 簡單檢查：如果 first 沒有句點且長度為 1 (如 "P")，補上句點
            if len(first) == 1 and first.isalpha():
                first += "."
            apa_authors.append(f"{last}, {first}")
    elif data.get('authors'):
        # Fallback: 如果沒解析成功，直接用原始字串
        apa_authors.append(data['authors'])

    # 組合作者字串
    if not apa_authors:
        auth_str = ""
    elif len(apa_authors) == 1:
        auth_str = apa_authors[0]
    elif len(apa_authors) == 2:
        # 兩位作者用 & 連接 (無逗號)
        auth_str = f"{apa_authors[0]} & {apa_authors[1]}"
    else:
        # 三位以上，最後一位前加 comma 和 &
        auth_str = ", ".join(apa_authors[:-1]) + f", & {apa_authors[-1]}"
    
    if auth_str and not auth_str.endswith('.'):
        auth_str += "."

    # === 2. 年份 (Year) ===
    # 格式: (2020).
    year_str = ""
    if data.get('year'):
        # 清理可能存在的括號，確保只有數字
        clean_year = str(data['year']).replace('(', '').replace(')', '').strip()
        year_str = f"({clean_year})."

    # === 3. 標題 (Title) ===
    # 格式: Title of the article.
    title_str = data.get('title', '').strip()
    if title_str:
        # 移除標題末尾原本的標點，統一加句號
        title_str = title_str.rstrip(',.;') 
        title_str += "."

    # === 4. 來源 (Source details) ===
    # 格式: *Journal Name*, *Volume*(Issue), Pages.
    # 注意: Markdown *text* 用於斜體
    source_parts = []
    
    # 來源名稱 (期刊/書名) -> 斜體
    if data.get('source'):
        source_parts.append(f"*{data['source']}*")
    
    # 卷號 (斜體) 與 期號 (括號，正體)
    if data.get('volume'):
        vol_info = f"*{data['volume']}*" # 卷號斜體
        if data.get('issue'):
            vol_info += f"({data['issue']})" # 期號緊接卷號，無空格
        source_parts.append(vol_info)
    elif data.get('issue'):
        # 只有期號的情況
        source_parts.append(f"({data['issue']})")
         
    # 頁碼
    if data.get('pages'):
        source_parts.append(data['pages'])

    # 組合來源字串
    source_str = ", ".join(source_parts)
    if source_str and not source_str.endswith('.'):
        source_str += "."

    # === 5. DOI / URL ===
    # 格式: https://doi.org/10.xxxx
    doi_str = ""
    if data.get('doi'):
        clean_doi = data['doi'].replace('doi:', '').strip()
        # 移除已經存在的 https://doi.org/ 前綴避免重複
        clean_doi = clean_doi.replace('https://doi.org/', '').replace('http://dx.doi.org/', '')
        doi_str = f"https://doi.org/{clean_doi}"
    elif data.get('url'):
        doi_str = data['url']

    # === 最終組合 ===
    # 過濾掉空字串並用空格連接
    parts = [p for p in [auth_str, year_str, title_str, source_str, doi_str] if p]
    return " ".join(parts)


def convert_zh_apa_to_num(data):
    parts = []
    # [UPDATED] 修正作者連接符號，list 轉字串
    if isinstance(data.get('authors'), list):
        auth = "、".join(data.get('authors'))
    else:
        auth = data.get('authors', '')
        
    if auth: parts.append(auth)
    if data.get('title'): parts.append(f"「{data['title']}」")
    # [UPDATED] 確保出處有被抓到才顯示
    if data.get('source'): parts.append(f"《{data['source']}》")
    if data.get('year'): parts.append(data['year'])
    return "，".join(parts) + "。"

def convert_zh_num_to_apa(data):
    # [UPDATED] 修正作者連接符號
    if isinstance(data.get('authors'), list):
        auth = "、".join(data.get('authors'))
    else:
        auth = data.get('authors', '')
        
    parts = []
    parts.append(f"{auth}（{data.get('year', '無年份')}）")
    if data.get('title'): parts.append(data['title'])
    if data.get('source'): parts.append(f"《{data['source']}》")
    return "。".join(parts) + "。"

# ==================== 5. JSON 暫存功能 ====================

def init_session_state():
    """session_state 是 Streamlit 的記憶體暫存機制，頁面重新整理後資料不會消失"""

    #儲存內文中的引用
    if 'in_text_citations' not in st.session_state: 
        st.session_state.in_text_citations = []
    # 儲存參考文獻列表
    if 'reference_list' not in st.session_state:
        st.session_state.reference_list = []
    # 儲存已透過 API 驗證過的正確文獻
    if 'verified_references' not in st.session_state:
        st.session_state.verified_references = []

def save_to_session(in_text_citations, reference_list):
    """將資料儲存到 session state"""
    st.session_state.in_text_citations = in_text_citations
    st.session_state.reference_list = reference_list

def export_to_json():
    """匯出為 JSON 格式: 將三個清單打包成一個 JSON 物件"""
    data = {
        "export_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "in_text_citations": st.session_state.in_text_citations,
        "reference_list": st.session_state.reference_list,
        "verified_references": st.session_state.verified_references
    }

    # ensure_ascii=False：保留中文字元, indent=2：格式化輸出，方便閱讀
    return json.dumps(data, ensure_ascii=False, indent=2)

def import_from_json(json_str):
    """從 JSON 匯入資料"""
    try:
        data = json.loads(json_str)
        st.session_state.in_text_citations = data.get("in_text_citations", [])
        st.session_state.reference_list = data.get("reference_list", [])
        st.session_state.verified_references = data.get("verified_references", [])
        return True, "資料匯入成功！"
    except Exception as e:
        return False, f"匯入失敗：{str(e)}"

def add_verified_reference(ref_data):
    """新增已驗證的文獻資料"""
    if 'verified_references' not in st.session_state:
        st.session_state.verified_references = []
    st.session_state.verified_references.append(ref_data)

# ==================== Streamlit UI ====================
st.set_page_config(page_title="文獻檢查系統 V3", layout="wide")
#st.set_page_config(page_title="文獻檢查系統 (Merged)", layout="wide")
# 初始化 session state
init_session_state()
st.title("📚 學術文獻引用檢查系統")
#st.title("🌏 全方位學術文獻分析與比對系統 (Merged)")

st.markdown("""
### ✨ 功能特色
1. ✅ **參考文獻檢查**：檢查文獻是否都被引用
2. ✅ **內文引用檢查**：檢查內文中的引用是否都對應參考文獻
3. ✅ **中英文辨識 & 格式轉換 (New)**：自動區分中英文、APA/IEEE 互轉
4. ✅ **深度欄位解析 (New)**：精準拆解作者、年份、篇名、DOI
5. ✅ **生成檢查報表**：輸出完整報告            
""")

st.markdown("---")

# ==================== JSON 資料管理區 ====================
with st.sidebar:
    st.header("💾 資料管理")
    
    # 顯示當前暫存狀態
    st.subheader("📊 當前暫存狀態")
    st.metric("內文引用數量", len(st.session_state.in_text_citations))
    st.metric("參考文獻數量", len(st.session_state.reference_list))
    st.metric("已驗證文獻", len(st.session_state.verified_references))
    
    st.markdown("---")
    
    # 匯出功能
    st.subheader("📤 匯出資料")
    if st.button("匯出為 JSON", use_container_width=True):
        json_data = export_to_json()
        st.download_button(
            label="📥 下載 JSON 檔案",
            data=json_data,
            file_name=f"citation_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True
        )
    
    # 匯入功能
    st.subheader("📥 匯入資料")
    uploaded_json = st.file_uploader("上傳 JSON 檔案", type=['json'])
    if uploaded_json:
        json_str = uploaded_json.read().decode('utf-8')
        success, message = import_from_json(json_str)
        if success:
            st.session_state.json_imported = True
            st.success(message)
        else:
            st.error(message)
            
    # 清除匯入標記（當檔案被移除時）
    if not uploaded_json and 'json_imported' in st.session_state:
        del st.session_state.json_imported
    
    # 清空資料
    st.markdown("---")
    st.subheader("🗑️ 清空資料")
    if st.button("清空所有暫存", type="secondary", use_container_width=True):
        st.session_state.in_text_citations = []
        st.session_state.reference_list = []
        st.session_state.verified_references = []
        st.success("已清空所有暫存資料")
        st.rerun() #重新載入頁面，更新側邊欄的數量顯示

uploaded_file = st.file_uploader("請上傳 Word 或 PDF 檔案", type=["docx", "pdf"])

# 如果有匯入的資料但沒有上傳檔案，顯示匯入的資料
if not uploaded_file and (st.session_state.in_text_citations or st.session_state.reference_list):
    st.info("📥 顯示已匯入的資料")

elif uploaded_file:
    # 清空舊資料，確保切換檔案時不會顯示舊分析結果
    st.session_state.in_text_citations = []
    st.session_state.reference_list = []
    if 'missing_refs' in st.session_state:
        del st.session_state.missing_refs
    if 'unused_refs' in st.session_state:
        del st.session_state.unused_refs

    file_ext = uploaded_file.name.split(".")[-1].lower()
    
    st.subheader(f"📄 處理檔案：{uploaded_file.name}")
    
    with st.spinner("正在讀取檔案..."):
        if file_ext == "docx":
            all_paragraphs = extract_paragraphs_from_docx(uploaded_file)
        elif file_ext == "pdf":
            all_paragraphs = extract_paragraphs_from_pdf(uploaded_file)
        else:
            st.error("不支援的檔案格式")
            st.stop()
    
    st.success(f"✅ 成功讀取 {len(all_paragraphs)} 個段落")
    
    st.markdown("---")
    
    content_paras, ref_paras, ref_start_idx, ref_keyword = classify_document_sections(all_paragraphs)
    
    
    
    st.subheader("🔍 內文引用分析")
    
    if content_paras:
        in_text_citations = extract_in_text_citations(content_paras)

        # 將內文引用轉換為可序列化格式並儲存 (確保可以轉為 JSON)
        serializable_citations = []
        for cite in in_text_citations:
            cite_dict = {
                'author': cite.get('author'),
                'co_author': cite.get('co_author'),
                'year': cite.get('year'),
                'ref_number': cite.get('ref_number'),
                'original': cite.get('original'),
                'normalized': cite.get('normalized'),
                'position': cite.get('position'),
                'type': cite.get('type'),
                'format': cite.get('format')
            }
            serializable_citations.append(cite_dict)
        
        # 儲存到 session state
        st.session_state.in_text_citations = serializable_citations
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border-radius: 12px;
                padding: 24px;
                text-align: center;
                color: white;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            ">
                <div style="font-size: 20px; opacity: 0.9; margin-bottom: 8px;">內文引用總數</div>
                <div style="font-size: 36px; font-weight: bold;">{len(in_text_citations)}</div>
            </div>
            """, unsafe_allow_html=True)
        
        apa_count = sum(1 for c in in_text_citations if c['format'] == 'APA')
        with col2:
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
                border-radius: 12px;
                padding: 24px;
                text-align: center;
                color: white;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            ">
                <div style="font-size: 20px; opacity: 0.9; margin-bottom: 8px;">APA 格式引用</div>
                <div style="font-size: 36px; font-weight: bold;">{apa_count}</div>
            </div>
            """, unsafe_allow_html=True)
        
        ieee_count = sum(1 for c in in_text_citations if c['format'] == 'IEEE')
        with col3:
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #0066cc 0%, #0080ff 100%);
                border-radius: 12px;
                padding: 24px;
                text-align: center;
                color: white;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            ">
                <div style="font-size: 20px; opacity: 0.9; margin-bottom: 8px;">IEEE 格式引用</div>
                <div style="font-size: 36px; font-weight: bold;">{ieee_count}</div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        if in_text_citations:
            with st.expander("📋 查看所有內文引用"):
                for i, cite in enumerate(in_text_citations, 1):
                    if cite['format'] == 'APA':
                        co_author_text = f" & {cite['co_author']}" if cite['co_author'] else ""
                        st.markdown(
                            f"{i}. `{cite['original']}` — "
                            f"**[{cite['format']}]** "
                            f"作者：**{cite['author']}{co_author_text}** | "
                            f"年份：**{cite['year']}** | "
                            f"類型：{cite['type']}"
                        )
                    else:
                        st.markdown(
                            f"{i}. `{cite['original']}` — "
                            f"**[{cite['format']}]** "
                            f"參考編號：**{cite['ref_number']}**"
                        )
        else:
            st.info("未找到任何內文引用")
    else:
        st.warning("無內文段落可供分析")
    
    st.markdown("---")
    
    if ref_paras:
        st.subheader("📖 參考文獻詳細解析與轉換 (整合版)")
        
        # [UPDATED from test1204-6] 自動偵測 IEEE 模式
        is_ieee_mode = False
        sample_count = min(len(ref_paras), 15)
        for i in range(sample_count):
            if re.match(r'^\s*[\[【]\s*\d+\s*[】\]]', ref_paras[i].strip()):
                is_ieee_mode = True
                break
        
        if is_ieee_mode:
            st.info("💡 偵測到 IEEE 編號格式 ([1], [2]...)，啟用**嚴格分割模式** (防止日期/DOI 斷行)")
            merged_refs = merge_references_ieee_strict(ref_paras)
        else:
            st.info("💡 偵測到一般格式 (APA/中文)，啟用**智慧混合模式**")
            merged_refs = merge_references_unified(ref_paras)
        
        # 使用新版的詳細解析引擎
        parsed_refs = [process_single_reference(r) for r in merged_refs]
        st.session_state.reference_list = parsed_refs
        
        st.info(f"成功解析出 {len(parsed_refs)} 筆參考文獻")
        
        # ==============================================================================
        # [NEW DISPLAY LOGIC] 仿照 1204github.py 的顯示風格 (卡片 + 分區 + Icon)
        # ==============================================================================
        
        # 1. 統計卡片區域
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border-radius: 12px;
                padding: 20px;
                text-align: center;
                color: white;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            ">
                <div style="font-size: 18px; opacity: 0.9; margin-bottom: 6px;">參考文獻總數</div>
                <div style="font-size: 28px; font-weight: bold;">{len(parsed_refs)}</div>
            </div>
            """, unsafe_allow_html=True)
        
        apa_refs_count = sum(1 for r in parsed_refs if 'APA' in r.get('format', ''))
        with col2:
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
                border-radius: 12px;
                padding: 20px;
                text-align: center;
                color: white;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            ">
                <div style="font-size: 18px; opacity: 0.9; margin-bottom: 6px;">APA 格式</div>
                <div style="font-size: 28px; font-weight: bold;">{apa_refs_count}</div>
            </div>
            """, unsafe_allow_html=True)
        
        ieee_refs_count = sum(1 for r in parsed_refs if 'IEEE' in r.get('format', ''))
        with col3:
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #0066cc 0%, #0080ff 100%);
                border-radius: 12px;
                padding: 20px;
                text-align: center;
                color: white;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            ">
                <div style="font-size: 18px; opacity: 0.9; margin-bottom: 6px;">IEEE 格式</div>
                <div style="font-size: 28px; font-weight: bold;">{ieee_refs_count}</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col4:
             st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #ff7675 0%, #ff9a3d 100%);
                border-radius: 12px;
                padding: 20px;
                text-align: center;
                color: white;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            ">
                <div style="font-size: 18px; opacity: 0.9; margin-bottom: 6px;">其他/混合</div>
                <div style="font-size: 28px; font-weight: bold;">0</div>
            </div>
            """, unsafe_allow_html=True)
             
        with col5:
             st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #95de64 0%, #b3e5fc 100%);
                border-radius: 12px;
                padding: 20px;
                text-align: center;
                color: #333;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            ">
                <div style="font-size: 18px; opacity: 0.9; margin-bottom: 6px;">未知格式</div>
                <div style="font-size: 28px; font-weight: bold;">0</div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # 2. IEEE 獨立展示區 (仿 1204 風格)
        st.markdown("### 📖 參考文獻詳細解析")
        ieee_list = [ref for ref in parsed_refs if 'IEEE' in ref.get('format', '')]
        
        if ieee_list:
            st.info(f"共找到 {len(ieee_list)} 筆 IEEE 格式參考文獻")
    
        for i, ref in enumerate(ieee_list, 1):
            # 準備顯示用的標題與圖示
            title_text = ref.get('title', '未提供標題')
            ref_num = ref.get('ref_number', str(i))
            
            # 根據 source_type 決定圖示與標籤
            stype = ref.get('source_type', 'Unknown')
            if 'Conference' in stype:
                icon = '🗣️'
            elif 'Journal' in stype:
                icon = '📚'
            elif 'Thesis' in stype:
                icon = '🎓'
            elif 'Website' in stype:
                icon = '🌐'
            elif 'Book' in stype:
                icon = '📖'
            elif 'Patent' in stype:
                icon = '💡'
            elif 'Report' in stype:
                icon = '📄'
            else:
                icon = '📄'

            # 展開區塊標題
            with st.expander(f"[{ref_num}] {title_text} ", expanded=False):
                
                c_info, c_action = st.columns([3, 1])
                
                with c_info:
                    # === 1. 作者 ===
                    if ref.get('authors'):
                        st.markdown(f"**👥 作者**")
                        # 如果有解析好的作者列表，優先使用
                        if ref.get('parsed_authors'):
                            # 將 [{'last': 'Lin', 'first': 'K. P.'}, ...] 轉為 "K. P. Lin"
                            auth_list = [f"{a.get('first', '')} {a.get('last', '')}".strip() for a in ref['parsed_authors']]
                            st.markdown(f"　└─ {', '.join(auth_list)}")
                        else:
                            # 否則直接顯示原始字串
                            st.markdown(f"　└─ {ref['authors']}")

                    # === 2. 標題 ===
                    if ref.get('title'):
                        st.markdown(f"**📝 標題**")
                        st.markdown(f"　└─ {ref['title']}")
                    
                    # === 3. 來源 (優先顯示具體名稱) ===
                    source_show = ref.get('conference_name') or ref.get('journal_name') or ref.get('source')
                    if source_show:
                        label = "會議名稱" if ref.get('conference_name') else ("期刊名稱" if ref.get('journal_name') else "來源出處")
                        st.markdown(f"**📖 {label}**")
                        st.markdown(f"　└─ {source_show}")
                    # === 4. 卷期與頁碼 (獨立顯示) ===
                    if ref.get('volume') or ref.get('issue'):
                        vol_str = f"Vol. {ref['volume']}" if ref.get('volume') else ""
                        issue_str = f"No. {ref['issue']}" if ref.get('issue') else ""
                        vi_display = ", ".join(filter(None, [vol_str, issue_str]))
                        
                        st.markdown(f"**📊 卷期**")
                        st.markdown(f"　└─ {vi_display}")
                    
                    if ref.get('pages'):
                        st.markdown(f"**📄 頁碼**")
                        st.markdown(f"　└─ pp. {ref['pages']}")
                        
                    # === 5. 年份與月份 (獨立顯示) ===
                    if ref.get('year'):
                        date_str = ref['year']
                        if ref.get('month'):
                            date_str = f"{ref['month']} {date_str}" # 例如: May 2014
                        st.markdown(f"**📅 年份**")
                        st.markdown(f"　└─ {date_str}")    
                    # === 4. 出版詳細資訊 (卷/期/頁/月/年) ===
                    # details = []
                    # if ref.get('volume'): details.append(f"Vol. {ref['volume']}")
                    # if ref.get('issue'): details.append(f"No. {ref['issue']}")
                    # if ref.get('pages'): details.append(f"pp. {ref['pages']}")
                    # if ref.get('month'): details.append(f"{ref['month']}")
                    # if ref.get('year'): details.append(f"{ref['year']}")
                    
                    # if details:
                    #     st.markdown(f"**📊 出版資訊**")
                    #     st.markdown(f"　└─ {', '.join(details)}")
                    
                    # # === 5. 出版社與地點 ===
                    # pub_loc = []
                    # if ref.get('publisher'): pub_loc.append(ref['publisher'])
                    # if ref.get('location'): pub_loc.append(ref['location'])
                    # if pub_loc:
                    #     st.markdown(f"**🏢 出版單位**")
                    #     st.markdown(f"　└─ {', '.join(pub_loc)}")

                    # === 6. 特殊編號 (報告號/專利號/版本) ===
                    extras = []
                    if ref.get('report_number'): extras.append(f"Report No.: {ref['report_number']}")
                    if ref.get('patent_number'): extras.append(f"Patent No.: {ref['patent_number']}")
                    if ref.get('edition'): extras.append(f"Edition: {ref['edition']}")
                    if extras:
                        st.markdown(f"**📌 其他資訊**")
                        for item in extras:
                            st.markdown(f"　└─ {item}")

                    # === 7. 電子資源 (DOI / URL) ===
                    if ref.get('doi'):
                        st.markdown(f"**🔍 DOI**")
                        st.markdown(f"　└─ [{ref['doi']}](https://doi.org/{ref['doi']})")
                        
                    if ref.get('url'):
                        st.markdown(f"**🌐 URL**")
                        st.markdown(f"　└─ [{ref['url']}]({ref['url']})")
                        if ref.get('access_date'):
                            st.caption(f"　　(Access Date: {ref['access_date']})")
                        
                    # === 8. 原文 ===
                    st.divider()
                    st.caption("📍 原始參考文獻文字")
                    st.code(ref['original'], language=None)
                
                with c_action:
                    st.markdown("**🛠️ 操作**")
                    # 這裡假設您有 convert_en_ieee_to_apa 函式
                    if st.button("轉 APA", key=f"ieee_btn_apa_{i}"):
                        st.code(convert_en_ieee_to_apa(ref), language='text')

                    # else:
                    #     st.info("未找到 IEEE 格式參考文獻")

            # st.markdown("---")

        # 3. APA 與其他格式展示區
        st.markdown("### 📚 APA 與其他格式參考文獻")
        apa_list = [ref for ref in parsed_refs if 'APA' in ref.get('format', '') or 'Numbered' in ref.get('format', '')]
        
        with st.expander("📋 查看 APA / 中文格式完整資訊"):
            for i, ref in enumerate(apa_list, 1):
                fmt = ref.get('format')
                title_display = ref.get('title') or "無標題"
                
                st.markdown(f"### {i}. [{fmt}]")
                
                c_info, c_action = st.columns([3, 1])
                
                with c_info:
                    # 作者顯示處理：如果是 list，根據語言合併成字串
                    authors_data = ref.get('authors')
                    if isinstance(authors_data, list):
                        if ref.get('lang') == 'ZH':
                            author_display = "、".join(authors_data)
                        else:
                            author_display = ", ".join(authors_data)
                    else:
                        author_display = authors_data or "Unknown"

                    st.markdown(f"**📝 作者**：{author_display}")
                    st.markdown(f"**📄 標題**：{title_display}")
                    # 顯示年份與月份
                    year_display = ref.get('year', 'Unknown')
                    if ref.get('month'):
                        year_display = f"{ref['year']} ({ref['month']})"
                    st.markdown(f"**📅 年份**：{year_display}")
                    
                    # 根據類型顯示來源/出版社
                    if ref.get('publisher'):
                        st.markdown(f"**🏢 出版社**：{ref['publisher']}")
                    elif ref.get('source'):
                        st.markdown(f"**📖 期刊/來源**：{ref.get('source')}")
                    
                    # 顯示卷期與頁碼/文章編號
                    pub_info = []
                    if ref.get('volume'):
                        pub_info.append(f"Vol. {ref['volume']}")
                    if ref.get('issue'):
                        pub_info.append(f"No. {ref['issue']}")

                    if pub_info:
                        st.markdown(f"**📊 卷期**：{', '.join(pub_info)}")

                    if ref.get('editors'):
                        st.markdown(f"**✍️ 編輯**：{ref['editors']}")
                    
                    if ref.get('book_title'):
                        st.markdown(f"**📚 書名**：{ref['book_title']}")

                    # 頁碼或文章編號
                    if ref.get('article_number'):
                        st.markdown(f"**📄 文章編號**：{ref['article_number']}")
                    elif ref.get('pages'):
                        st.markdown(f"**📄 頁碼**：{ref['pages']}")
                    
                    # 顯示 DOI
                    if ref.get('doi'):
                        st.markdown(f"**🔍 DOI**：[{ref['doi']}](https://doi.org/{ref['doi']})")
                    # 顯示 URL
                    elif ref.get('url'):
                        st.markdown(f"**🌐 URL**：[{ref['url']}]({ref['url']})")
                    
                    st.text_area(
                        label="原文",
                        value=ref['original'],
                        height=80,
                        key=f"apa_orig_{i}",
                        disabled=True
                    )
                
                with c_action:
                    st.markdown("**🛠️ 格式轉換**")
                    if ref.get('lang') == 'EN':
                        if st.button("轉 IEEE", key=f"apa_btn_ieee_{i}"):
                            st.code(convert_en_apa_to_ieee(ref), language='text')
                    elif ref.get('lang') == 'ZH':
                        if 'APA' in fmt:
                            if st.button("轉編號", key=f"zh_btn_num_{i}"):
                                st.code(convert_zh_apa_to_num(ref), language='text')
                        elif 'Numbered' in fmt:
                            if st.button("轉 APA", key=f"zh_btn_apa_{i}"):
                                st.code(convert_zh_num_to_apa(ref), language='text')
                
                st.markdown("---")

        ## ==================== [舊的顯示邏輯 - 已註解保留] ====================
        ## 這是原本 test_extraction.py 的顯示方式 (簡單列表)，現已被上方 1204 風格取代
        ##
        ## with st.expander("🔍 點擊展開詳細清單與格式轉換工具"):
        ##     for i, ref in enumerate(parsed_refs, 1):
        ##         lang_tag = "🇹🇼 中文" if ref.get('lang') == 'ZH' else "🇺🇸 英文"
        ##         fmt = ref.get('format', 'Unknown')
        ##         title = ref.get('title') or "無標題"
        ##         
        ##         st.markdown(f"**{i}. [{lang_tag}] {title}**")
        ##         
        ##         c_info, c_action = st.columns([3, 1])
        ##         with c_info:
        ##             st.caption(f"格式: {fmt} | 年份: {ref.get('year')} | 作者: {ref.get('author')}")
        ##             #st.text(ref['original'])
        ##             st.text_area("原文", ref['original'], height=70, disabled=True, key=f"orig_text_{i}")
        ##         
        ##         with c_action:
        ##             # [Test1201] 格式轉換按鈕區
        ##             if ref.get('lang') == 'EN':
        ##                 if 'APA' in fmt:
        ##                     if st.button("轉 IEEE", key=f"btn_ieee_{i}"):
        ##                         st.code(convert_en_apa_to_ieee(ref))
        ##                 elif 'IEEE' in fmt:
        ##                     if st.button("轉 APA", key=f"btn_apa_{i}"):
        ##                         st.code(convert_en_ieee_to_apa(ref))
        ##             elif ref.get('lang') == 'ZH':
        ##                 if 'APA' in fmt:
        ##                     if st.button("轉編號", key=f"btn_num_{i}"):
        ##                         st.code(convert_zh_apa_to_num(ref))
        ##                 elif 'Numbered' in fmt:
        ##                     if st.button("轉 APA", key=f"btn_zhapa_{i}"):
        ##                         st.code(convert_zh_num_to_apa(ref))
        ##         st.divider()
        ## ==================================================================== 
           
    else:
        st.warning("無參考文獻段落可供分析")

st.markdown("---")

st.header("🚀 交叉比對分析")
st.info("👆 請確認上方解析結果無誤後，點擊下方按鈕開始檢查。")

if st.button("開始交叉比對", type="primary", use_container_width=True):
    if not st.session_state.in_text_citations or not st.session_state.reference_list:
        st.error("❌ 資料不足，無法比對。請確認是否已成功解析內文引用與參考文獻。")
    else:
        with st.spinner("正在進行雙向交叉比對..."):
                # 呼叫我們剛寫好的 check_references 函式
            missing, unused = check_references(
                st.session_state.in_text_citations,
                st.session_state.reference_list
                )
                
                # 將結果存入 session state 以便顯示
            st.session_state.missing_refs = missing
            st.session_state.unused_refs = unused
                
            st.success("✅ 比對完成！")

    # ==========================================
    # 第三階段：顯示比對結果報告
    # ==========================================
    
    # 檢查 session state 中是否有比對結果，有的話才顯示
    if 'missing_refs' in st.session_state and 'unused_refs' in st.session_state:
        st.subheader("📊 比對結果報告")
        
        # 使用 Tabs 分頁顯示兩類錯誤
        tab1, tab2 = st.tabs([
            f"❌ 遺漏的參考文獻 ({len(st.session_state.missing_refs)})", 
            f"⚠️ 未使用的參考文獻 ({len(st.session_state.unused_refs)})"
        ])
        
        with tab1:
            st.caption("💡 說明：這些引用出現在內文中，但在參考文獻列表裡找不到對應項目。")
    
            if not st.session_state.missing_refs:
                st.success("太棒了！所有內文引用都在參考文獻列表中找到了。")
            else:
                for i, item in enumerate(st.session_state.missing_refs, 1):
            # 檢查是否為「疑似年份錯誤」
                    if item.get('error_type') == 'year_mismatch':
                        st.warning(
                    f"{i}. **{item['original']}** (格式: {item['format']})\n\n"
                    f"⚠️ **疑似年份引用錯誤**：系統在參考文獻中找到了同名作者，"
                    f"但年份似乎是 **{item.get('year_hint', '不同年份')}**，而非內文寫的 **{item.get('year')}**。",
                    icon="📅"
                )
            # 如果不是年份錯誤，就是真的找不到 (Missing)
                    else:
                        st.error(f"{i}. **{item['original']}** (格式: {item['format']})", icon="🚨")


        with tab2:
            st.caption("💡 說明：這些文獻列在參考文獻列表中，但在內文中從未被引用過。")
            if not st.session_state.unused_refs:
                st.success("太棒了！所有參考文獻都在內文中被有效引用。")
            else:
                for i, item in enumerate(st.session_state.unused_refs, 1):
                    # 使用黃色警告，並顯示原始文字
                    st.warning(f"{i}. **{item['original']}**", icon="🗑️")

# ==================== 查看暫存資料 ====================
if st.session_state.in_text_citations or st.session_state.reference_list:
    with st.expander("🔍 查看完整暫存資料（JSON 格式）"):
        st.json({
            "in_text_citations": st.session_state.in_text_citations,
            "reference_list": st.session_state.reference_list,
            "verified_references": st.session_state.verified_references
        })