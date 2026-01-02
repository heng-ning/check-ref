# reference_router.py
import re
from utils.text_processor import normalize_text, has_chinese
from parsers.apa.apa_parser_en import extract_apa_en_detailed
from parsers.apa.apa_parser_zh import extract_apa_zh_detailed
from parsers.ieee.ieee_parser import extract_ieee_reference_full


def is_ieee_like(ref_text: str) -> bool:
    """
    偵測非 [n] 開頭，但實際上是 IEEE / RFC / Online 類型的文獻
    （例如：F. Hao, “Schnorr ...”, RFC 8235, Sep. 2017. [Online].）
    """
    return (
        # IEEE initials 作者格式：F. Hao, / J. K. Smith,
        re.match(r'^\s*(?:[A-Z]\.\s*){1,3}[A-Za-z\-]+,\s+', ref_text)
        or '“' in ref_text
        or '[Online]' in ref_text
        or 'Available:' in ref_text
        or re.search(r'\bRFC\s+\d+', ref_text)
    )


def process_single_reference(ref_text: str) -> dict:
    """
    核心分流邏輯：
    - 開頭是 [n]/【n】 → IEEE
    - 非 [n] 但看起來像 IEEE → IEEE
    - 其他 → APA EN / APA ZH
    """
    ref_text = normalize_text(ref_text)

    # === IEEE: [1] / 【1】 開頭 ===
    if re.match(r'^\s*[\[【]', ref_text):
        data = extract_ieee_reference_full(ref_text)

    # === IEEE-like（沒有 [n]，但實際是 IEEE / RFC / Online）===
    elif is_ieee_like(ref_text):
        data = extract_ieee_reference_full(ref_text)

    # === APA ===
    else:
        if has_chinese(ref_text):
            data = extract_apa_zh_detailed(ref_text)
        else:
            data = extract_apa_en_detailed(ref_text)

    # === 作者欄位統一輸出 ===
    authors = data.get("authors")
    if isinstance(authors, list):
        data["author"] = " ".join(authors)
    elif isinstance(authors, str):
        data["author"] = authors
    else:
        data["author"] = "Unknown"

    return data
