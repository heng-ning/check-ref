"""
參考文獻格式驗證模組
檢查 IEEE 和 APA 格式的參考文獻是否符合基本格式標準
"""
import re
from typing import Dict, List, Tuple


def validate_ieee_format(ref: dict, index: int) -> Tuple[bool, List[str]]:
    """
    驗證 IEEE 格式參考文獻的基本格式要求
    
    Args:
        ref: 參考文獻字典
        index: 參考文獻索引（用於錯誤訊息）
    
    Returns:
        (is_valid, error_messages): 是否有效及錯誤訊息列表
    """
    errors = []
    original = ref.get('original', '')
    
    # 1. 必須有編號
    if not ref.get('ref_number'):
        errors.append(f"缺少編號（應以 [n] 或 【n】 開頭）")
    
    # 2. 必須有作者
    authors = ref.get('authors') or ref.get('parsed_authors')
    if not authors:
        errors.append(f"無法解析作者（必要比對條件）：可能為團體作者、專案名稱或格式非標準")
    elif isinstance(authors, list) and len(authors) == 0:
        errors.append(f"作者列表為空")
    
    # 3. 必須有標題
    title = ref.get('title')
    original = ref.get('original', '')

    # 特殊情況：學位論文可能用 "Dissertation - 標題" 格式，解析器可能無法提取
    # 如果原文包含 "Dissertation"/"Thesis" 等關鍵字，且有破折號，視為有標題
    is_thesis_format = bool(re.search(r'(Dissertation|Thesis|碩士|博士)\s*[-–—]\s*', original))

    if not title and not is_thesis_format:
        errors.append(f"缺少文獻標題")
    
    # 4. 必須有年份
    year = ref.get('year')
    original = ref.get('original', '')

    if not year:
        # 檢查原文是否包含民國年份（民國 XXX 年）或其他年份格式
        has_minguo_year = bool(re.search(r'民國\s*\d{2,3}\s*年', original))
        has_year_in_original = bool(re.search(r'(19\d{2}|20[0-2]\d|民國\s*\d{2,3})', original))
        
        if not has_year_in_original:
            errors.append(f"缺少出版年份")
    else:
        # 驗證年份格式（1900-2026 或民國年）
        year_str = str(year)
        if not re.search(r'(19\d{2}|20[0-2]\d|\d{2,3})', year_str):
            errors.append(f"年份格式不正確：{year}")
    
    # 5. 檢查基本格式結構（作者名字格式）
    if isinstance(authors, list) and authors:
        # IEEE 格式應該是 "First Last" 或有 parsed_authors
        first_author = str(authors[0]) if authors else ""
        # 如果不是英文作者（中文等），跳過格式檢查
        if first_author and re.search(r'[a-zA-Z]', first_author):
            # 檢查是否有逗號分隔（IEEE 不應該用 "Last, F." 格式）
            if ',' in first_author and not ref.get('parsed_authors'):
                errors.append(f"作者格式可能不符合 IEEE 標準（應為 'First Last' 而非 'Last, F.'）")
    
    # 6. 期刊論文應有卷期或文章編號或 DOI (允許 Early Access、預印本和純電子期刊)
    if ref.get('journal_name') or ref.get('source'):
        # 檢查是否為中文參考文獻（通常包含中文標點或「卷」「期」「頁」等字）
        original = ref.get('original', '')
        is_chinese = bool(re.search(r'[\u4e00-\u9fff]', original))
        
        # 中文參考文獻跳過格式檢查（因為解析器可能無法正確提取所有欄位）
        if is_chinese:
            pass  # 不檢查中文期刊論文的卷期頁碼
        else:
            has_volume = ref.get('volume')
            has_issue = ref.get('issue')
            has_article_number = ref.get('article_number')
            has_pages = ref.get('pages')
            has_doi = ref.get('doi')
            has_url = ref.get('url')  # 新增：檢查網址
            is_early_access = 'early access' in original.lower()
            
            # 檢查是否為預印本
            source = (ref.get('source') or ref.get('journal_name') or '').lower()
            is_preprint = 'arxiv' in source or 'preprint' in source or 'biorxiv' in source or 'medrxiv' in source
            
            # 允許以下任一情況：
            # - 有卷期/頁碼（傳統格式）
            # - 有文章編號（純電子期刊）
            # - 有 DOI 且標註 Early Access
            # - 預印本（arXiv 等）
            # - 有網址（學位論文、技術報告等）
            if not (has_volume or has_article_number or has_pages or (has_doi and is_early_access) or is_preprint or has_url):
                if has_doi and not is_early_access:
                    errors.append(f"期刊論文有 DOI 但缺少卷期/頁碼/文章編號，如為預刊請標註 'early access'")
                else:
                    errors.append(f"期刊論文缺少卷期、文章編號、頁碼、DOI 或網址資訊")
    
    return len(errors) == 0, errors


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
        if format_type == 'IEEE':
            is_valid, errors = validate_ieee_format(ref, i)
        else:  # APA
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

    # authors 欄位在 IEEE/APA 可能不同
    if format_type == "IEEE":
        authors = ref.get("authors") or ref.get("parsed_authors")
    else:
        authors = ref.get("authors") or ref.get("author")

    if not authors or (isinstance(authors, list) and len(authors) == 0):
        errors.append("無法解析作者（必要比對條件）：可能為團體作者、專案名稱或格式非標準")

    year = ref.get("year")
    if not year:
        # 你的 IEEE 原本有做「原文是否有年份」的容錯，我保留這個邏輯
        has_year_in_original = bool(re.search(r'(?<!\d)(19\d{2}|20[0-2]\d)(?!\d)|民國\s*\d{2,3}', original))
        if not has_year_in_original:
            errors.append("缺少出版年份（必要比對條件）")

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
        warnings.append("缺少文獻標題（非必要欄位，仍可比對，但解析資訊不完整）")

    # DOI / URL
    if not ref.get("doi") and not ref.get("url"):
        warnings.append("缺少 DOI/URL（非必要欄位）")

    # 出處（source / journal / conference / publisher 任一）
    has_venue = bool(ref.get("source") or ref.get("journal_name") or ref.get("conference_name") or ref.get("publisher"))
    if not has_venue:
        warnings.append("缺少出處/來源資訊（期刊/會議/出版社等）（非必要欄位）")

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
