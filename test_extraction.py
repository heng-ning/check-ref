import streamlit as st
import re
import unicodedata
from docx import Document
import fitz
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


# ==================== 1. 文件讀取模組 ====================

def extract_paragraphs_from_docx(file):
    doc = Document(file)
    return [para.text.strip() for para in doc.paragraphs if para.text.strip()]

# def extract_paragraphs_from_pdf(file):
#     text = ""
#     with fitz.open(stream=file.read(), filetype="pdf") as doc:
#         for page in doc:
#             page_text = page.get_text("text")
#             text += page_text + "\n"
#     paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
#     return paragraphs

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
    """改進的參考文獻區段識別"""
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
        return paragraphs, [], None, None
    
    content_paragraphs = paragraphs[:ref_start_index]
    return content_paragraphs, ref_paragraphs, ref_start_index, ref_keyword


# ==================== 3. 內文引用擷取 ====================

def is_valid_year(year_str):
    try:
        year = int(year_str)
        return 1000 <= year <= 2050
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


# ==================== 4. 參考文獻解析 ====================

def find_apa(ref_text):
    """
    改進：支援 (2007, October 11) / (2011, Jan. 14) / (n.d.)
    """
    ref_text = normalize_text(ref_text)

    apa_match = re.search(
        r'[（(]\s*(\d{4}(?:[a-c])?|n\.d\.)\s*(?:,\s*(?:[A-Za-z]+\.?\s*\d{0,2}))?\s*[)）]',
        ref_text, re.IGNORECASE
    )

    if not apa_match:
        return False

    year_str = apa_match.group(1)[:4]
    year_pos = apa_match.start(1)
    pre_context = ref_text[max(0, year_pos - 5):year_pos]
    if re.search(r'\d', pre_context):  # 避免 887(2020) 誤判
        return False

    return year_str.isdigit() or apa_match.group(1).lower() == "n.d."

def find_apalike(ref_text):
    valid_years = []
    for match in re.finditer(r'[,，.。]\s*(\d{4}[a-c]?)[.。，]', ref_text):
        year_str = match.group(1)
        year_pos = match.start(1)
        year_core = year_str[:4]
        if not is_valid_year(year_core): continue
        pre_context = ref_text[max(0, year_pos - 5):year_pos]
        if re.search(r'\d', pre_context): continue
        after_context = ref_text[match.end(1):match.end(1) + 5]
        if re.match(r'\.(\d{1,2}|[a-z0-9]{2,})', after_context, re.IGNORECASE): continue
        arxiv_pattern = re.compile(
            r'arxiv:\d{4}\.\d{5}[^a-zA-Z0-9]{0,3}\s*[,，]?\s*' + re.escape(year_str), re.IGNORECASE
        )
        if arxiv_pattern.search(ref_text) and arxiv_pattern.search(ref_text).start() < year_pos: continue
        valid_years.append((year_str, year_pos))
    for match in re.finditer(r'，\s*(\d{4}[a-c]?)\s*，\s*。', ref_text):
        year_str = match.group(1)
        year_pos = match.start(1)
        year_core = year_str[:4]
        if not is_valid_year(year_core): continue
        pre_context = ref_text[max(0, year_pos - 5):year_pos]
        if re.search(r'\d', pre_context): continue
        valid_years.append((year_str, year_pos))
    return valid_years

def is_reference_head(para):
    return bool(find_apa(para) or re.match(r"^\[\d+\]", para) or find_apalike(para))

def find_apa_matches(ref_text):
    APA_PATTERN = r'[（(](\d{4}[a-c]?|n\.d\.)\s*(?:,\s*[A-Za-z]+\s*\d{1,2})?\s*[）)]?[。\.]?'
    matches = []
    for m in re.finditer(APA_PATTERN, ref_text, re.IGNORECASE):
        year_str = m.group(1)[:4]
        year_pos = m.start(1)
        pre_context = ref_text[max(0, year_pos - 5):year_pos]
        if re.search(r'\d', pre_context): continue
        if year_str.isdigit() and is_valid_year(year_str):
            matches.append(m)
        elif m.group(1).lower() == "n.d.":
            matches.append(m)
    return matches

def find_apalike_matches(ref_text):
    matches = []
    pattern1 = r'[,，.。]\s*(\d{4}[a-c]?)[.。，]'
    for m in re.finditer(pattern1, ref_text):
        year_str = m.group(1)
        year_pos = m.start(1)
        year_core = year_str[:4]
        if not is_valid_year(year_core): continue
        pre_context = ref_text[max(0, year_pos - 5):year_pos]
        after_context = ref_text[m.end(1):m.end(1) + 5]
        if re.search(r'\d', pre_context): continue
        if re.match(r'\.(\d{1,2}|[a-z0-9]{2,})', after_context, re.IGNORECASE): continue
        arxiv_pattern = re.compile(
            r'arxiv:\d{4}\.\d{5}[^a-zA-Z0-9]{0,3}\s*[,，]?\s*' + re.escape(year_str), re.IGNORECASE
        )
        if arxiv_pattern.search(ref_text) and arxiv_pattern.search(ref_text).start() < year_pos: continue
        matches.append(m)
    pattern2 = r'，\s*(\d{4}[a-c]?)\s*，\s*。'
    for m in re.finditer(pattern2, ref_text):
        year_str = m.group(1)
        year_pos = m.start(1)
        year_core = year_str[:4]
        pre_context = ref_text[max(0, year_pos - 5):year_pos]
        if re.search(r'\d', pre_context): continue
        if is_valid_year(year_core):
            matches.append(m)
    return matches

def split_multiple_apa_in_paragraph(paragraph):
    apa_matches = find_apa_matches(paragraph)
    apalike_matches = find_apalike_matches(paragraph)
    all_matches = apa_matches + apalike_matches
    all_matches.sort(key=lambda m: m.start())
    if len(all_matches) < 2:
        return [paragraph]
    split_indices = []
    for match in all_matches[1:]:
        cut_index = max(0, match.start() - 5)
        split_indices.append(cut_index)
    segments = []
    start = 0
    for idx in split_indices:
        segments.append(paragraph[start:idx].strip())
        start = idx
    segments.append(paragraph[start:].strip())
    return [s for s in segments if s]

def merge_references_by_heads(paragraphs):
    merged = []
    for para in paragraphs:
        apa_count = 1 if find_apa(para) else 0
        apalike_count = len(find_apalike(para))
        if apa_count >= 2 or apalike_count >= 2:
            sub_refs = split_multiple_apa_in_paragraph(para)
            merged.extend([s.strip() for s in sub_refs if s.strip()])
        else:
            if is_reference_head(para):
                merged.append(para.strip())
            else:
                if merged:
                    merged[-1] += " " + para.strip()
                else:
                    merged.append(para.strip())
    return merged

def detect_reference_format(ref_text):
    """偵測參考文獻格式"""
    if re.match(r'^\s*[【\[]\s*\d+\s*[】\]]\s*', ref_text):
        return 'IEEE'
    
    if find_apa(ref_text):
        return 'APA'
    
    if find_apalike(ref_text):
        return 'APA_LIKE'
    
    return 'Unknown'


# ==================== 修正版：IEEE 文獻資訊擷取 ====================

def extract_ieee_reference_info_fixed(ref_text):
    """修正版 IEEE 格式擷取（修復多作者問題）"""
    
    number_match = re.match(r'^\s*[\[【]\s*(\d+)\s*[\]】]\s*', ref_text)
    if not number_match:
        return None
    
    ref_number = number_match.group(1)
    rest_text = ref_text[number_match.end():].strip()
    
    authors = "Unknown"
    title = None
    year = "Unknown"
    
    # 步驟 1：優先找引號中的標題
    quote_patterns = [
        (r'"', r'"'),
        (r'“', r'”'),
        (r'「', r'」'),
        (r'\'', r'\''),
        (r'“', r'“'),
        (r'”', r'”'),
    ]
    
    title_found = False
    
    for open_q, close_q in quote_patterns:
        pattern = re.escape(open_q) + r'(.+?)' + re.escape(close_q)
        match = re.search(pattern, rest_text)
        
        if match:
            title = match.group(1).strip()
            title = re.sub(r'[,，.。;；:：]*$', '', title).strip()
            
            # 引號前的所有內容都是作者（包含多作者）
            before_title = rest_text[:match.start()].strip()
            before_title = before_title.rstrip(',，. ')
            
            # 移除可能的 "and" 結尾
            before_title = re.sub(r'\s+and\s*$', '', before_title, flags=re.IGNORECASE)
            # 移除 et al. 結尾
            before_title = re.sub(r',?\s*et\s+al\.?$', '', before_title, flags=re.IGNORECASE)
            
            if before_title:
                # 清理開頭的編號殘留
                before_title = re.sub(r'^\[\d+\]\s*', '', before_title)
                
                # 完整保留所有作者（用逗號分隔的多作者）
                if re.search(r'[a-zA-Z\u4e00-\u9fff]', before_title) and len(before_title) > 1:
                    authors = before_title  # 保留完整多作者字串
            
            title_found = True
            break
    
    # 如果沒有找到引號標題，用備選方案
    if not title_found:
        # 嘗試用 "and" 判斷作者區段結尾
        and_match = re.search(r'\band\b', rest_text, re.IGNORECASE)
        
        if and_match:
            after_and = rest_text[and_match.end():].strip()
            next_comma = after_and.find(',')
            
            if next_comma > 0:
                # 從開頭到 "and" 後第一個逗號為作者
                authors_section = rest_text[:and_match.end() + next_comma].strip()
                authors_section = authors_section.rstrip(',，. ')
                
                # 完整保留作者區段
                if authors_section and re.search(r'[a-zA-Z]', authors_section):
                    authors = authors_section
                
                # 逗號後的內容為標題候選
                remaining = rest_text[and_match.end() + next_comma:].strip()
                remaining = remaining.lstrip(',，. ')
                
                title_match = re.match(r'^([^,，.。]+)', remaining)
                if title_match:
                    potential_title = title_match.group(1).strip()
                    if len(potential_title) > 10:
                        title = potential_title
        else:
            # 沒有 "and"，嘗試用第一個逗號分隔
            parts = rest_text.split(',', 2)
            
            if len(parts) >= 2:
                potential_author = parts[0].strip()
                if potential_author and re.search(r'[a-zA-Z]', potential_author):
                    authors = potential_author
                
                potential_title = parts[1].strip()
                if len(potential_title) > 10:
                    title = potential_title
    
    # 提取年份
    year_matches = re.findall(r'\b(19\d{2}|20\d{2})\b', rest_text)
    if year_matches:
        year = year_matches[-1]
    
    return {
        'ref_number': ref_number,
        'authors': authors,
        'title': title if title else "Unknown",
        'year': year
    }

def extract_ieee_reference_full(ref_text):
    """
    完整解析 IEEE 格式參考文獻
    返回：格式、文獻類型、所有欄位
    """
    
    # 基本欄位初始化
    result = {
        'format': 'IEEE',
        'ref_number': None,
        'source_type': 'Unknown',
        'authors': None,
        'title': None,
        'journal_name': None,
        'conference_name': None,
        'book_title': None,
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
    
    # 提取編號
    number_match = re.match(r'^\s*[\[【]\s*(\d+)\s*[\]】]\s*', ref_text)
    if not number_match:
        return result
    
    result['ref_number'] = number_match.group(1)
    rest_text = ref_text[number_match.end():].strip()
    
    # === 1. 提取作者和標題（使用你的引號偵測邏輯） ===
    authors = "Unknown"
    title = None
    
    # 優先找引號中的標題（作者與標題分界點）
    quote_patterns = [
        (r'"', r'"'),
        (r'"', r'"'),
        (r'「', r'」'),
        (r'“', r'”'),
        (r'“', r'“') ,
        (r'\'', r'\''),
        (r'”', r'”')
    ]
    
    title_found = False
    after_title = rest_text
    
    for open_q, close_q in quote_patterns:
        pattern = re.escape(open_q) + r'(.+?)' + re.escape(close_q)
        match = re.search(pattern, rest_text)
        
        if match:
            title = match.group(1).strip()
            title = re.sub(r'[,，.。;；:：]*$', '', title).strip()
            result['title'] = title
            
            # 引號前的所有內容都是作者（包含多作者）
            before_title = rest_text[:match.start()].strip()
            before_title = before_title.rstrip(',，. ')
            
            # 移除可能的 "and" 結尾
            before_title = re.sub(r'\s+and\s*$', '', before_title, flags=re.IGNORECASE)
            # 移除 et al. 結尾
            before_title = re.sub(r',?\s*et\s+al\.?$', '', before_title, flags=re.IGNORECASE)
            
            if before_title:
                # 清理開頭的編號殘留
                before_title = re.sub(r'^\[\d+\]\s*', '', before_title)
                
                # 完整保留所有作者（用逗號分隔的多作者）
                if re.search(r'[a-zA-Z\u4e00-\u9fff]', before_title) and len(before_title) > 1:
                    authors = before_title
            
            result['authors'] = authors
            after_title = rest_text[match.end():].strip()
            title_found = True
            break
    
    # 如果沒有找到引號標題，用備選方案
    if not title_found:
        # 嘗試用 "and" 判斷作者區段結尾
        and_match = re.search(r'\band\b', rest_text, re.IGNORECASE)
        
        if and_match:
            after_and = rest_text[and_match.end():].strip()
            next_comma = after_and.find(',')
            
            if next_comma > 0:
                # 從開頭到 "and" 後第一個逗號為作者
                authors_section = rest_text[:and_match.end() + next_comma].strip()
                authors_section = authors_section.rstrip(',，. ')
                
                # 完整保留作者區段
                if authors_section and re.search(r'[a-zA-Z]', authors_section):
                    authors = authors_section
                    result['authors'] = authors
                
                # 逗號後的內容為標題候選
                remaining = rest_text[and_match.end() + next_comma:].strip()
                remaining = remaining.lstrip(',，. ')
                
                title_match = re.match(r'^([^,，.。]+)', remaining)
                if title_match:
                    potential_title = title_match.group(1).strip()
                    if len(potential_title) > 10:
                        title = potential_title
                        result['title'] = title
                
                after_title = remaining
        else:
            # 沒有 "and"，嘗試用第一個逗號分隔
            parts = rest_text.split(',', 2)
            
            if len(parts) >= 2:
                potential_author = parts[0].strip()
                if potential_author and re.search(r'[a-zA-Z]', potential_author):
                    authors = potential_author
                    result['authors'] = authors
                
                potential_title = parts[1].strip()
                if len(potential_title) > 10:
                    title = potential_title
                    result['title'] = title
                
                if len(parts) >= 3:
                    after_title = parts[2]
    
    # === 2. 判斷文獻類型 ===
    if re.search(r'\bin\b.*(Proc\.|Proceedings|Conference|Symposium|Workshop)', after_title, re.IGNORECASE):
        result['source_type'] = 'Conference Paper'
        conf_match = re.search(r'\bin\s+(.+?)(?:,|\d{4})', after_title, re.IGNORECASE)
        if conf_match:
            result['conference_name'] = conf_match.group(1).strip()
    
    elif re.search(r'(vol\.|volume|no\.|number)', after_title, re.IGNORECASE):
        result['source_type'] = 'Journal Article'
        journal_match = re.search(r'^([^,]+)', after_title)
        if journal_match:
            result['journal_name'] = journal_match.group(1).strip()
    
    elif re.search(r'\[Online\]|Available:|https?://', after_title, re.IGNORECASE):
        result['source_type'] = 'Website/Online'

    elif re.search(r'\[Online\]|Available:|https?://|arxiv\.org', after_title, re.IGNORECASE):
        result['source_type'] = 'Website/Online'

    elif re.search(r'(Ph\.D\.|M\.S\.|thesis|dissertation)', after_title, re.IGNORECASE):
        result['source_type'] = 'Thesis/Dissertation'
    
    elif re.search(r'(Tech\. Rep\.|Technical Report)', after_title, re.IGNORECASE):
        result['source_type'] = 'Technical Report'
    
    elif re.search(r'Patent', after_title, re.IGNORECASE):
        result['source_type'] = 'Patent'
    
    elif re.search(r'(Ed\.|Eds\.|edition)', after_title, re.IGNORECASE):
        result['source_type'] = 'Book'
    
    # === 3. 提取通用欄位 ===

    # 卷號
    vol_match = re.search(r'vol\.\s*(\d+)', after_title, re.IGNORECASE)
    if vol_match:
        result['volume'] = vol_match.group(1)

    # 期號
    issue_match = re.search(r'no\.\s*(\d+)', after_title, re.IGNORECASE)
    if issue_match:
        result['issue'] = issue_match.group(1)

    # 頁碼（改進：更精確的匹配，避免抓到授權資訊中的數字）
    pages_match = re.search(r'pp\.\s*([\d]+\s*[–\-—]\s*[\d]+)', after_title, re.IGNORECASE)
    if pages_match:
        # 清理頁碼中的空格
        pages = pages_match.group(1)
        pages = re.sub(r'\s+', '', pages)  # 移除空格
        pages = pages.replace('–', '-').replace('—', '-')  # 統一連字符
        result['pages'] = pages

    # 年份
    year_matches = re.findall(r'\b(19\d{2}|20\d{2})\b', after_title)
    if year_matches:
        result['year'] = year_matches[0]  # 取第一個年份（避免抓到下載日期）

    # 月份
    month_match = re.search(r'\b(Jan\.|Feb\.|Mar\.|Apr\.|May|Jun\.|Jul\.|Aug\.|Sep\.|Oct\.|Nov\.|Dec\.)\b', 
                        after_title, re.IGNORECASE)
    if month_match:
        result['month'] = month_match.group(1)

    # URL（改進：支援 arXiv、GitHub 等各種 URL，含空格處理）
    url = None

    # 1. 優先直接抓 Available: / Retrieved from 後的網址，全長且允許空白
    url_match = re.search(r'(?:Available:|Retrieved from)\s*(https?://[^\s,]+(?:\s+[^\s,]+)*)', after_title, re.IGNORECASE)
    if url_match:
        # 合併所有換行與空白使其為一行
        url = url_match.group(1).strip().replace(' ', '')

    # 2. 如果沒抓到，再抓所有 http 開頭到遇到空白/逗號/句號/結尾
    if not url:
        generic_url_match = re.search(r'(https?://[^\s,.;]+)', after_title)
        if generic_url_match:
            url = generic_url_match.group(1).strip()

    # 3. 最後寫入 result
    if url:
        result['url'] = url

    # 存取日期（改進：更精確匹配）
    access_match = re.search(
        r'(?:accessed|retrieved|downloaded)\s+(?:on\s+)?([A-Za-z]+\.?\s+\d{1,2},?\s*\d{4})', 
        after_title, 
        re.IGNORECASE
    )
    if access_match:
        result['access_date'] = access_match.group(1)

    # DOI（新增：支援多種 DOI 格式）
    doi_patterns = [
        r'doi:\s*(10\.\d{4,}/[^\s,]+)',  # 標準格式：doi: 10.xxxx/xxxxx
        r'https?://(?:dx\.)?doi\.org/(10\.\d{4,}/[^\s,]+)',  # URL 格式：https://doi.org/10.xxxx/xxxxx
        r'DOI:\s*(10\.\d{4,}/[^\s,]+)',  # 大寫 DOI
    ]

    for pattern in doi_patterns:
        doi_match = re.search(pattern, after_title, re.IGNORECASE)
        if doi_match:
            result['doi'] = doi_match.group(1).rstrip('.,;')
            break

    # 出版社與地點
    publisher_match = re.search(
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s+([A-Z]{2,}(?:,\s+[A-Z]{2,})?)\s*:\s*([^,]+)', 
        after_title
    )
    if publisher_match:
        result['location'] = publisher_match.group(1) + ', ' + publisher_match.group(2)
        result['publisher'] = publisher_match.group(3)

    # 版本
    edition_match = re.search(r'(\d+(?:st|nd|rd|th)\s+ed\.)', after_title, re.IGNORECASE)
    if edition_match:
        result['edition'] = edition_match.group(1)

    # 報告編號
    report_match = re.search(r'(Tech\.\s+Rep\.|Rep\.)\s+([\w\-]+)', after_title, re.IGNORECASE)
    if report_match:
        result['report_number'] = report_match.group(2)

    # 專利號
    patent_match = re.search(r'(U\.S\.|US)\s+Patent\s+([\d,]+)', after_title, re.IGNORECASE)
    if patent_match:
        result['patent_number'] = patent_match.group(2)
    
    return result



def extract_apa_reference_info_fixed(ref_text):
    """
    APA 格式擷取（修正多作者問題 + 支援完整日期 + 改進標題擷取）
    """
    
    # 找年份（必須有括號,支援完整日期格式）
    year_match = re.search(
        r'[（(]\s*(\d{4}[a-z]?|n\.d\.)\s*(?:,\s*([A-Za-z]+\.?\s*\d{0,2}))?\s*[）)]',
        ref_text, 
        re.IGNORECASE
    )
    
    if not year_match:
        return {
            'author': 'Unknown',
            'year': 'Unknown',
            'date': None,
            'title': None
        }
    
    year_text = year_match.group(1)
    year = year_text[:4] if year_text.lower() != 'n.d.' else 'n.d.'
    
    # 提取完整日期（如果有月份日期）
    date_str = year_match.group(2) if year_match.group(2) else None
    
    # 提取作者（年份前的內容）
    before_year = ref_text[:year_match.start()].strip()
    author = "Unknown"
    
    if before_year:
        # 移除末尾的標點和空格
        before_year = before_year.rstrip(',，. ')
        
        # 檢查長度和內容
        if 2 <= len(before_year) <= 300:
            # 排除無效的作者名
            invalid_patterns = [
                r'^\d+$',  # 純數字
                r'^[，,\.。]+$',  # 純標點
            ]
            
            is_valid = True
            for pattern in invalid_patterns:
                if re.match(pattern, before_year, re.IGNORECASE):
                    is_valid = False
                    break
            
            # 直接使用整個 before_year（保留多作者）
            if is_valid and re.search(r'[a-zA-Z\u4e00-\u9fff]', before_year):
                author = before_year
    
    # 提取標題（年份後的內容）
    after_year = ref_text[year_match.end():].strip()
    title = None
    
    if after_year:
        # 移除開頭的標點符號和空格
        after_year = re.sub(r'^[\s.,，。)\]】]+', '', after_year)
        
        if after_year:
            # 先處理特殊情況：斜體標記
            after_year = re.sub(r'</?i>', '', after_year)
            
            # 1. 先找是否有明確的標題結束標記
            title_end_markers = [
                r'Retrieved from',
                r'Available from',
                r'Available at',
                r'\[Electronic version\]',
                r'DOI:',
                r'doi:',
                r'https?://',
            ]
            
            title_end_pos = len(after_year)
            for marker in title_end_markers:
                match = re.search(marker, after_year, re.IGNORECASE)
                if match and match.start() < title_end_pos:
                    title_end_pos = match.start()
            
            # 取標題結束標記前的內容
            title_candidate = after_year[:title_end_pos].strip()
            
            # 2. 清理標題末尾
            # 移除末尾的期刊資訊標記
            title_candidate = re.sub(
                r'\s*[\.,]\s*$',
                '',
                title_candidate
            )
            
            # 移除可能的期刊名稱（斜體標記後的內容）
            # 例如: "Title. Journal Name" -> "Title"
            if '.' in title_candidate:
                parts = title_candidate.split('.')
                # 如果第一部分夠長,就用第一部分
                if len(parts[0].strip()) >= 10:
                    title_candidate = parts[0].strip()
            
            # 3. 驗證標題
            if len(title_candidate) >= 5:
                if not re.match(r'^(Retrieved|Available|DOI|doi|https?|www)', title_candidate, re.IGNORECASE):
                    if not (title_candidate.isupper() and len(title_candidate) < 20):
                        title = title_candidate
    
    return {
        'author': author,
        'year': year,
        'date': date_str,
        'title': title
    }

def extract_apalike_reference_info_fixed(ref_text):
    """修正版 APA_LIKE 格式擷取"""
    
    years = find_apalike(ref_text)
    
    if not years:
        return {
            'author': 'Unknown',
            'year': 'Unknown',
            'title': None,
            'format': 'APA_LIKE'
        }
    
    year_str, year_pos = years[-1]
    year = year_str[:4]
    
    before_year = ref_text[:year_pos].strip()
    
    author = "Unknown"
    title = None
    
    parts = re.split(r'[,，.。]', before_year)
    parts = [p.strip() for p in parts if p.strip()]
    
    if parts:
        if parts[0] and re.search(r'[a-zA-Z\u4e00-\u9fff]', parts[0]):
            author = parts[0]
        
        if len(parts) > 1:
            potential_title = parts[1]
            if potential_title and len(potential_title) > 5:
                title = potential_title
    
    return {
        'author': author,
        'year': year,
        'title': title,
        'format': 'APA_LIKE'
    }


def merge_ieee_references(ref_paragraphs):
    """增強版 IEEE 段落合併"""
    merged = []
    current_ref = ""
    
    for para in ref_paragraphs:
        para = para.strip()
        if not para:
            continue
        
        if re.match(r'^\s*[【\[]\s*\d+\s*[】\]]\s*', para):
            if current_ref:
                merged.append(current_ref.strip())
            current_ref = para
            continue
        
        if len(para) < 20:
            current_ref += " " + para
            continue
        
        if re.match(r'^[a-z]', para):
            current_ref += " " + para
            continue
        
        if re.match(r'^[,，.。;；:"\'\-]', para):
            current_ref += " " + para
            continue
        
        if any(keyword in para for keyword in ['http', 'doi:', 'DOI:', '[Online]', 'Available', '.pdf', '.doi']):
            current_ref += " " + para
            continue
        
        if current_ref and not re.search(r'[.。!！?？]$', current_ref.strip()):
            current_ref += " " + para
            continue
        
        if re.match(r'^[A-Z][a-z]+(?:\s+and\s+|\s*,\s*)', para):
            current_ref += " " + para
            continue
        
        if current_ref:
            current_ref += " " + para
        else:
            current_ref = para
    
    if current_ref:
        merged.append(current_ref.strip())
    
    return merged


def extract_reference_info(ref_paragraphs):
    """從參考文獻段落中提取基本資訊（使用修正版）"""
    if not ref_paragraphs:
        return []
    
    first_ref = normalize_text(ref_paragraphs[0])
    is_ieee_format = re.match(r'^\s*[【\[]\s*\d+\s*[】\]]\s*', first_ref)
    
    if is_ieee_format:
        ref_paragraphs = merge_ieee_references(ref_paragraphs)
    
    ref_list = []
    
    for ref_text in ref_paragraphs:
        format_type = detect_reference_format(ref_text)
        
        if format_type == 'IEEE':
            ieee_info = extract_ieee_reference_info_fixed(ref_text)
            
            if ieee_info:
                ref_list.append({
                    'author': ieee_info['authors'],
                    'year': ieee_info['year'],
                    'date': None,
                    'ref_number': ieee_info['ref_number'],
                    'title': ieee_info['title'],
                    'format': 'IEEE',
                    'original': ref_text
                })
            else:
                ref_list.append({
                    'author': 'Parse Error',
                    'year': 'Unknown',
                    'date': None,
                    'ref_number': 'Unknown',
                    'title': None,
                    'format': 'IEEE',
                    'original': ref_text
                })
        
        elif format_type == 'APA':
            apa_info = extract_apa_reference_info_fixed(ref_text)
            ref_list.append({
                'author': apa_info['author'],
                'year': apa_info['year'],
                'date': apa_info.get('date'), 
                'ref_number': None,
                'title': apa_info['title'],
                'format': 'APA',
                'original': ref_text
            })
        
        elif format_type == 'APA_LIKE':
            apalike_info = extract_apalike_reference_info_fixed(ref_text)
            ref_list.append({
                'author': apalike_info['author'],
                'year': apalike_info['year'],
                'date': None,
                'ref_number': None,
                'title': apalike_info['title'],
                'format': 'APA_LIKE',
                'original': ref_text
            })
        
        else:
            ref_list.append({
                'author': 'Unknown Format',
                'year': 'Unknown',
                'date': None,
                'ref_number': None,
                'title': None,
                'format': 'Unknown',
                'original': ref_text
            })
    
    return ref_list

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

st.set_page_config(page_title="文獻檢查系統", layout="wide")
# 初始化 session state
init_session_state()

st.title("📚 學術文獻引用檢查系統")

st.markdown("""
### ✨ 功能特色
1. ✅ **參考文獻檢查**：檢查文獻是否都被引用
2. ✅ **內文引用檢查**：檢查內文中的引用是否都對應參考文獻
3. ✅ **文獻真實性驗證**：透過 DOI/ISBN/線上資料庫驗證
4. ✅ **格式一致性檢查**：檢查格式是否符合學術規範
5. ✅ **格式轉換工具**：提供 APA/IEEE 等格式相互轉換
6. ✅ **生成檢查報表**：輸出完整報告            
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
    
    st.markdown("---")
    
    st.subheader("🔍 內文引用分析（APA + IEEE）")
    
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
    
    st.subheader("📖 參考文獻完整解析")
    
    if ref_paras:
        apa_refs_merged = merge_references_by_heads(ref_paras)
        ref_info = extract_reference_info(apa_refs_merged)

        # 將參考文獻轉換為可序列化格式並儲存
        serializable_refs = []
        for ref in ref_info:
            ref_dict = {
                'author': ref.get('author'),
                'year': ref.get('year'),
                'date': ref.get('date'),
                'ref_number': ref.get('ref_number'),
                'title': ref.get('title'),
                'format': ref.get('format'),
                'original': ref.get('original')
            }
            serializable_refs.append(ref_dict)
        
        # 儲存到 session state
        st.session_state.reference_list = serializable_refs

        # APA主鍵: 第一作者+年份
        apa_citation_pairs = set(
            (c['author'].strip().lower(), c['year'])
            for c in in_text_citations
            if c['format']=="APA" and c['author'] and c['year']
        )
        ref_pairs = set()
        for ref in apa_refs_merged:
            info = extract_apa_reference_info_fixed(ref)
            if info['author'] and info['year']:
                ref_pairs.add((info['author'].strip().lower(), info['year']))
        unused_apa = [ref for ref in apa_refs_merged if
                    (extract_apa_reference_info_fixed(ref)['author'].strip().lower(),
                    extract_apa_reference_info_fixed(ref)['year']) not in apa_citation_pairs]
        uncited_apa = [f"{author}, {year}" for author, year in (apa_citation_pairs - ref_pairs)]

        # IEEE主鍵: 編號
        in_text_ieee_set = set(
            c['ref_number'].strip() for c in in_text_citations if c['format']=='IEEE' and c.get('ref_number')
        )
        ieee_ref_numbers = set()
        for ref in ref_paras:
            m = re.match(r'^\s*[\[【](\d+)[】\]]', ref)
            if m:
                ieee_ref_numbers.add(m.group(1).strip())
        unused_ieee_refs = [ref for ref in ref_paras if (
            (m := re.match(r'^\s*[\[【](\d+)[】\]]', ref)) and m.group(1).strip() not in in_text_ieee_set)]
        uncited_ieee = in_text_ieee_set - ieee_ref_numbers

        # 統一展示（不用分格式，只分清單類型）
        tab1, tab2, tab3 = st.tabs(['未被引用文獻','未列出引用','合併預覽'])
        with tab1:
            count = 0
            for r in unused_apa:
                count += 1
                st.write(f"{count}. {r}")
            for r in unused_ieee_refs:
                count += 1
                st.write(f"{count}. {r}")
            if count == 0:
                st.success("所有參考文獻都已被引用")

        with tab2:
            count = 0
            for c in uncited_apa:
                count += 1
                st.write(f"{count}. {c}")
            for num in uncited_ieee:
                count += 1
                st.write(f"{count}. IEEE編號[{num}]")
            if count == 0:
                st.success("所有引用都出現在參考文獻")

        with tab3:
            for i, r in enumerate(apa_refs_merged[:10], 1):
                st.write(f"{i}. {r}")

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
                <div style="font-size: 28px; font-weight: bold;">{len(ref_info)}</div>
            </div>
            """, unsafe_allow_html=True)
        
        apa_refs = sum(1 for r in ref_info if r['format'] == 'APA')
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
                <div style="font-size: 28px; font-weight: bold;">{apa_refs}</div>
            </div>
            """, unsafe_allow_html=True)
        
        ieee_refs = sum(1 for r in ref_info if r['format'] == 'IEEE')
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
                <div style="font-size: 28px; font-weight: bold;">{ieee_refs}</div>
            </div>
            """, unsafe_allow_html=True)
        
        apalike_refs = sum(1 for r in ref_info if r['format'] == 'APA_LIKE')
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
                <div style="font-size: 18px; opacity: 0.9; margin-bottom: 6px;">APA_LIKE</div>
                <div style="font-size: 28px; font-weight: bold;">{apalike_refs}</div>
            </div>
            """, unsafe_allow_html=True)
        
        unknown_refs = sum(1 for r in ref_info if r['format'] == 'Unknown')
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
                <div style="font-size: 28px; font-weight: bold;">{unknown_refs}</div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # ============ IEEE 獨立展示（避免巢狀 expander）============
        st.markdown("### 📖 IEEE 參考文獻詳細解析")
        
        ieee_list = [ref for ref in ref_info if ref['format'] == 'IEEE']
        
        if ieee_list:
            st.info(f"共找到 {len(ieee_list)} 筆 IEEE 格式參考文獻")
            
            for i, ref in enumerate(ieee_list, 1):
                ieee_data = extract_ieee_reference_full(ref['original'])
                
                type_icons = {
                    'Conference Paper': '📄',
                    'Journal Article': '📚',
                    'Book': '📖',
                    'Website/Online': '🌐',
                    'Thesis/Dissertation': '🎓',
                    'Technical Report': '📋',
                    'Patent': '⚖️',
                    'Unknown': '❓'
                }
                icon = type_icons.get(ieee_data['source_type'], '📄')
                
                with st.expander(
                    f"{icon} [{ieee_data['ref_number']}] {ieee_data['source_type']} - {ieee_data['title'] or '未提供標題'}",
                    expanded=False
                ):
                    if ieee_data['authors']:
                        st.markdown(f"**👥 作者**")
                        st.markdown(f"　└─ {ieee_data['authors']}")
                    
                    if ieee_data['title']:
                        st.markdown(f"**📝 標題**")
                        st.markdown(f"　└─ {ieee_data['title']}")
                    
                    if ieee_data['source_type'] == 'Conference Paper':
                        if ieee_data['conference_name']:
                            st.markdown(f"**🎯 會議名稱**")
                            st.markdown(f"　└─ {ieee_data['conference_name']}")
                    
                    elif ieee_data['source_type'] == 'Journal Article':
                        if ieee_data['journal_name']:
                            st.markdown(f"**📖 期刊名稱**")
                            st.markdown(f"　└─ {ieee_data['journal_name']}")
                        vol_issue = []
                        if ieee_data['volume']:
                            vol_issue.append(f"Vol. {ieee_data['volume']}")
                        if ieee_data['issue']:
                            vol_issue.append(f"No. {ieee_data['issue']}")
                        if vol_issue:
                            st.markdown(f"**📊 卷期**")
                            st.markdown(f"　└─ {', '.join(vol_issue)}")
                    
                    elif ieee_data['source_type'] == 'Website/Online':
                        if ieee_data['url']:
                            st.markdown(f"**🔗 URL**")
                            st.markdown(f"　└─ [{ieee_data['url']}]({ieee_data['url']})")
                        if ieee_data['access_date']:
                            st.markdown(f"**📅 存取日期**")
                            st.markdown(f"　└─ {ieee_data['access_date']}")
                    
                    time_info = []
                    if ieee_data['year']:
                        time_info.append(f"📅 年份：{ieee_data['year']}")
                    if ieee_data['month']:
                        time_info.append(f"📆 月份：{ieee_data['month']}")
                    if time_info:
                        st.markdown(f"**⏰ 時間資訊**")
                        st.markdown(f"　└─ {' | '.join(time_info)}")
                    
                    if ieee_data['pages']:
                        st.markdown(f"**📄 頁碼**")
                        st.markdown(f"　└─ pp. {ieee_data['pages']}")
                    
                    if ieee_data['doi']:
                        st.markdown(f"**🔍 DOI**")
                        st.markdown(f"　└─ {ieee_data['doi']}")
                    
                    st.markdown("**📍 原文**")
                    st.code(ieee_data['original'], language=None)
        else:
            st.info("未找到 IEEE 格式參考文獻")
        
        st.markdown("---")
        
        # ============ APA 和其他格式 ============
        st.markdown("### 📚 APA 與其他格式參考文獻")
        
        with st.expander("📋 查看 APA / APA_LIKE / 未知格式完整資訊"):
            for i, ref in enumerate(ref_info, 1):
                if ref['format'] == 'APA':
                    title_display = ref['title'] if ref['title'] else "❌ 無法擷取"
                    st.markdown(f"### {i}. [APA]")
                    st.markdown(f"**📝 作者**：{ref['author']}")
                    st.markdown(f"**📄 標題**：{title_display}")
                    st.markdown(f"**📅 年份**：{ref['year']}")
                    if ref.get('date'):
                        st.markdown(f"**🗓️ 時間**：{ref['date']}")
                    
                    st.text_area(
                        label="原文",
                        value=ref['original'],
                        height=80,
                        key=f"ref_original_apa_{len(st.session_state.reference_list)}_{i}",
                        disabled=True
                    )
                    st.markdown("---")
                        
                elif ref['format'] == 'APA_LIKE':
                    st.markdown(f"### {i}. [APA_LIKE]")
                    st.markdown(f"**📅 年份**：{ref['year']}")
                    st.text_area(
                        label="原文",
                        value=ref['original'],
                        height=80,
                        key=f"ref_original_apalike_{len(st.session_state.reference_list)}_{i}",
                        disabled=True
                    )
                    st.markdown("---")
                        
                elif ref['format'] == 'Unknown':
                    st.markdown(f"### {i}. [未知格式]")
                    st.markdown("**⚠️ 無法解析格式**")
                    st.text_area(
                        label="原文",
                        value=ref['original'],
                        height=80,
                        key=f"ref_original_unknown_{len(st.session_state.reference_list)}_{i}",
                        disabled=True
                    )
                    st.markdown("---")
                    
                elif ref['format'] == 'APA_LIKE':
                    st.markdown(f"### {i}. [APA_LIKE]")
                    st.markdown(f"**📅 年份**：{ref['year']}")
                    st.text_area(
                        label="原文",
                        value=ref['original'],
                        height=80,
                        key=f"ref_original_apalike_{i}",
                        disabled=True
                    )
                    st.markdown("---")
                    
                elif ref['format'] == 'Unknown':
                    st.markdown(f"### {i}. [未知格式]")
                    st.markdown("**⚠️ 無法解析格式**")
                    st.text_area(
                        label="原文",
                        value=ref['original'],
                        height=80,
                        key=f"ref_original_unknown_{i}",
                        disabled=True
                    )
                    st.markdown("---")
    else:
        st.warning("無參考文獻段落可供分析")

st.markdown("---")
st.markdown("""
---
📌 **使用提示**：
- 上傳 PDF/Word 檔案後，系統會自動解析並暫存資料
- 使用側邊欄的「資料管理」功能來匯出/匯入 JSON
- JSON 資料可用於後續與外部 API 比對
""")

# ==================== 查看暫存資料 ====================
if st.session_state.in_text_citations or st.session_state.reference_list:
    with st.expander("🔍 查看完整暫存資料（JSON 格式）"):
        st.json({
            "in_text_citations": st.session_state.in_text_citations,
            "reference_list": st.session_state.reference_list,
            "verified_references": st.session_state.verified_references
        })
