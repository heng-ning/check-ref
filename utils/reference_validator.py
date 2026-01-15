"""
參考文獻格式驗證模組
檢查 APA 格式的參考文獻是否符合基本格式標準
"""
import re
from typing import Dict, List, Tuple

def validate_apa_format(ref: dict, index: int) -> Tuple[bool, List[str]]:
    """
    驗證 APA 格式參考文獻的基本格式要求
    
    Args:
        ref: 參考文獻字典
        index: 參考文獻索引（用於錯誤訊息）
    
    Returns:
        (is_valid, error_messages): 是否有效及錯誤訊息列表
    """
    errors = []
    original = ref.get('original', '')
    lang = ref.get('lang', 'EN')
    
    # 1. 必須有作者
    authors = ref.get('authors') or ref.get('author')
    if not authors:
        errors.append(f"無法解析作者（必要比對條件）：可能為團體作者、專案名稱或格式非標準")
    elif isinstance(authors, list) and len(authors) == 0:
        errors.append(f"作者列表為空")
    
    # 2. 必須有年份
    year = ref.get('year')
    if not year:
        errors.append(f"缺少出版年份")
    else:
        # 驗證年份格式
        year_str = str(year)
        if not re.search(r'(19\d{2}|20[0-2]\d)', year_str):
            errors.append(f"年份格式不正確：{year}")
    
    # 3. 必須有標題
    if not ref.get('title'):
        errors.append(f"缺少文獻標題")
    
    # 4. 檢查作者格式（英文 APA）
    # if lang == 'EN' and isinstance(authors, list) and authors:
    #     first_author = str(authors[0])
    #     # APA 英文格式應該是 "Last, F. M." 或類似格式
    #     if re.search(r'[a-zA-Z]', first_author):
    #         # 檢查是否有逗號（APA 要求姓在前，名縮寫在後）
    #         if ',' not in first_author:
    #             # 可能是 "First Last" 格式，不符合 APA
    #             if ' ' in first_author.strip():
    #                 errors.append(f"作者格式可能不符合 APA 標準（應為 'Last, F.' 而非 'First Last'）")
    
    # 5. 期刊論文應有來源資訊
    if ref.get('document_type') in ['期刊論文', 'Journal Article', None]:
        has_source = ref.get('source') or ref.get('journal_name')
        has_volume = ref.get('volume')
        has_publisher = ref.get('publisher')
        
        # 檢查是否為中文參考文獻
        original = ref.get('original', '')
        is_chinese = bool(re.search(r'[\u4e00-\u9fff]', original))
        
        # 檢查是否為書籍（有出版社、沒有期刊名、有出版地點）
        # APA 書籍格式：作者 (年份), "書名", 出版社, 出版地點.
        has_location = bool(re.search(r',\s*[A-Z][a-z]+\s*\.?\s*$', original))  # 例如 ", New York."

        # 檢查原文是否包含常見出版社名稱
        common_publishers = [
            'mcgraw', 'hill', 'wiley', 'springer', 'elsevier', 'oxford', 'cambridge',
            'pearson', 'routledge', 'sage', 'taylor', 'francis', 'academic press',
            'mit press', 'harvard', 'princeton', 'prentice hall', 'addison wesley'
        ]
        original_lower = original.lower()
        has_publisher_name = any(pub in original_lower for pub in common_publishers)

        likely_book = has_publisher or has_location or has_publisher_name
        
        if not has_source:
            # 檢查是否為書籍章節或預印本
            is_book_chapter = ref.get('book_title') or has_publisher
            source_lower = (ref.get('source') or '').lower()

            # 同時檢查原文中是否包含預印本關鍵字
            original_lower = original.lower()
            is_preprint = (
                'arxiv' in source_lower or 
                'preprint' in source_lower or
                'arxiv' in original_lower or 
                'preprint' in original_lower or
                'biorxiv' in original_lower or
                'medrxiv' in original_lower or
                'ssrn' in original_lower  # 社會科學預印本
            )
            
            # 檢查原文是否包含期刊特徵（有卷號、頁碼、斜體等）
            has_volume_in_text = bool(re.search(r'Vol\.\s*\d+|Volume\s*\d+|卷\s*\d+', original, re.IGNORECASE))
            has_pages_in_text = bool(re.search(r'pp?\.\s*\d+|頁\s*\d+', original, re.IGNORECASE))
            likely_has_journal = has_volume or has_volume_in_text or has_pages_in_text
            
            # 中文參考文獻、書籍、或明顯有期刊特徵但解析失敗，跳過檢查
            if not is_chinese and not is_book_chapter and not is_preprint and not likely_has_journal and not likely_book:
                errors.append(f"缺少期刊名稱或出版資訊")
    
    # 6. 檢查不應該有編號（APA 不使用編號）
    if ref.get('ref_number'):
        errors.append(f"APA 格式不應包含編號 [{ref.get('ref_number')}]")
    
    return len(errors) == 0, errors


def validate_reference_list(reference_list: List[dict], format_type: str = 'auto') -> Tuple[bool, List[Dict]]:
    """
    驗證整個參考文獻列表
    
    Args:
        reference_list: 參考文獻列表
        format_type: 'IEEE', 'APA', 或 'auto' (自動判斷)
    
    Returns:
        (all_valid, validation_results): 
            - all_valid: 是否所有文獻都有效
            - validation_results: 驗證結果列表，每項包含 {index, ref_number, original, is_valid, errors}
    """
    if not reference_list:
        return True, []
    
    # 自動判斷格式（基於第一筆參考文獻）
    if format_type == 'auto':
        first_ref = reference_list[0]
        if first_ref.get('ref_number'):
            format_type = 'IEEE'
        else:
            format_type = 'APA'
    
    validation_results = []
    all_valid = True
    
    for i, ref in enumerate(reference_list, 1):
        # 根據格式類型選擇驗證函數
        if format_type == 'APA':
            is_valid, errors = validate_apa_format(ref, i)
        
        # 記錄驗證結果
        result = {
            'index': i,
            'ref_number': ref.get('ref_number', i),
            'original': ref.get('original', '')[:100] + '...' if len(ref.get('original', '')) > 100 else ref.get('original', ''),
            'is_valid': is_valid,
            'errors': errors,
            'format_type': format_type
        }
        
        validation_results.append(result)
        
        if not is_valid:
            all_valid = False
    
    return all_valid, validation_results


def get_validation_summary(validation_results: List[Dict]) -> Dict:
    """
    生成驗證摘要
    
    Args:
        validation_results: 驗證結果列表
    
    Returns:
        摘要字典，包含總數、有效數、無效數等統計資訊
    """
    total = len(validation_results)
    valid_count = sum(1 for r in validation_results if r['is_valid'])
    invalid_count = total - valid_count
    
    # 統計常見錯誤類型
    error_types = {}
    for result in validation_results:
        if not result['is_valid']:
            for error in result['errors']:
                # 提取錯誤類型（取第一個詞）
                error_type = error.split('：')[0].split('（')[0]
                error_types[error_type] = error_types.get(error_type, 0) + 1
    
    return {
        'total': total,
        'valid_count': valid_count,
        'invalid_count': invalid_count,
        'validity_rate': (valid_count / total * 100) if total > 0 else 0,
        'error_types': error_types,
        'format_type': validation_results[0]['format_type'] if validation_results else 'Unknown'
    }
# reference_validator.py (新增：折衷版驗證)

from typing import Dict, List, Tuple

def validate_required_fields(ref: dict, format_type: str) -> Tuple[bool, List[str]]:
    """
    只檢查『交叉比對必要條件』：作者 + 年份
    缺任一項 -> critical error
    """
    errors = []
    original = ref.get("original", "")
    if format_type == "APA":
      # authors 欄位在 APA 可能不同
      authors = ref.get("authors") or ref.get("author")

      if not authors or (isinstance(authors, list) and len(authors) == 0):
          errors.append("作者資訊不足（可能因文獻未提供或系統解析限制，影響比對）")

      year = ref.get("year")
      if not year:
          # 只檢查原文是否有西元年 (不含民國)
          has_year_in_original = bool(re.search(r'(?<!\d)(19\d{2}|20[0-2]\d)(?!\d)', original))
          if not has_year_in_original:
              errors.append("年份資訊不足（可能因文獻未提供或系統解析限制或年份非西元年格式（目前僅支援西元年比對），影響比對）")

    return (len(errors) == 0), errors


def validate_optional_fields(ref: dict, format_type: str) -> Tuple[bool, List[str]]:
    """
    非必要欄位：缺了不擋比對，但要回報 warnings
    例如：title / doi / source 等
    """
    warnings = []
    original = ref.get("original", "")

    # 標題（你們最常痛的）
    title = ref.get("title")
    # IEEE 你原本對 thesis 有特例；這裡也沿用（避免誤殺）
    is_thesis_format = bool(re.search(r'(Dissertation|Thesis|碩士|博士)\s*[-–—]\s*', original))
    if (not title) and (not is_thesis_format):
        warnings.append("文獻標題未能解析（可能因格式非標準或解析限制，仍可比對，但解析資訊不完整）")

    # DOI / URL
    #if not ref.get("doi") and not ref.get("url"):
    #    warnings.append("缺少 DOI/URL（非必要欄位）")

    # 出處（source / journal / conference / publisher 任一）
    has_venue = bool(ref.get("source") or ref.get("journal_name") or ref.get("conference_name") or ref.get("publisher"))
    if not has_venue:
        warnings.append("出處／來源資訊未能解析（可能因格式非標準或解析限制，不影響比對）")

    return (len(warnings) == 0), warnings


def validate_reference_list_relaxed(reference_list: List[dict], format_type: str = "auto") -> Tuple[bool, List[Dict], List[Dict]]:
    """
    折衷版：
    - critical_results：必要條件（作者+年份）缺失 -> 會導致報錯停止
    - warning_results：其他欄位缺失 -> 只顯示警告但不停止
    Returns:
      (critical_ok, critical_results, warning_results)
    """
    if not reference_list:
        return False, [], []

    # auto 判斷沿用原本邏輯
    if format_type == "auto":
        first_ref = reference_list[0]
        format_type = "IEEE" if first_ref.get("ref_number") else "APA"

    critical_ok = True
    critical_results = []
    warning_results = []

    for i, ref in enumerate(reference_list, 1):
        ok_req, req_errors = validate_required_fields(ref, format_type)
        ok_opt, opt_warnings = validate_optional_fields(ref, format_type)

        short_original = ref.get("original", "")
        short_original = short_original[:100] + "..." if len(short_original) > 100 else short_original

        if not ok_req:
            critical_ok = False
            critical_results.append({
                "index": i,
                "ref_number": ref.get("ref_number", i),
                "original": short_original,
                "errors": req_errors,
                "format_type": format_type
            })

        if not ok_opt:
            warning_results.append({
                "index": i,
                "ref_number": ref.get("ref_number", i),
                "original": short_original,
                "warnings": opt_warnings,
                "format_type": format_type
            })

    return critical_ok, critical_results, warning_results
