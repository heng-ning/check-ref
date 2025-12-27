import re
import unicodedata

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

def is_valid_year(year_str):
    try:
        year = int(year_str)
        return 1500 <= year <= 2050
    except:
        return False
    
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
