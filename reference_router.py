# reference_router.py
import re
from utils.text_processor import normalize_text, has_chinese
from parsers.apa.apa_parser_en import extract_apa_en_detailed
from parsers.apa.apa_parser_zh import extract_apa_zh_detailed
from parsers.ieee.ieee_parser import extract_ieee_reference_full

def process_single_reference(ref_text: str) -> dict:
    """
    核心分流邏輯：
    - 開頭是 [n]/【n】 → 走 IEEE 解析（內部再判斷是否 inline APA）
    - 否則 → 依語言走 APA EN / APA ZH
    """
    ref_text = normalize_text(ref_text)

    if re.match(r'^\s*[\[【]', ref_text):
        data = extract_ieee_reference_full(ref_text)
    else:
        if has_chinese(ref_text):
            data = extract_apa_zh_detailed(ref_text)
        else:
            data = extract_apa_en_detailed(ref_text)

    authors = data.get("authors")
    if isinstance(authors, list):
        data["author"] = " ".join(authors)
    elif isinstance(authors, str):
        data["author"] = authors
    else:
        data["author"] = "Unknown"

    return data
