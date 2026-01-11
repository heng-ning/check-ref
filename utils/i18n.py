import streamlit as st

# =============================================================================
# 1. 多語言字典 (整合 app.py 與 components.py 的所有 key)
# =============================================================================
TRANSLATIONS = {
    "zh": {
        # App 介面
        "page_title": "📚 學術文獻引用檢查系統",
        "features_title": "### ✨ 功能特色",
        "feature_1": "1. ✅ **參考文獻完整性檢查**：比對「參考文獻列表」與「內文引用」，找出遺漏引用與未使用文獻。",
        "feature_2": "2. ✅ **內文引用一致性檢查**：檢查內文中的作者、年份或編號是否都能正確對應到參考文獻。",
        "feature_3": "3. ✅ **中英混合與格式自動辨識**：智慧偵測 APA / IEEE / 中文數字編號等格式，並支援中英文文獻混排。",
        "feature_4": "4. ✅ **深度欄位解析與格式轉換**：精準拆解作者、年份、篇名、期刊／會議名稱、頁碼、DOI、URL，並提供 APA ⇄ IEEE、自編號 ⇄ APA 等互轉。",
        "feature_5": "5. ✅ **互動式檢查報表與匯出**：在介面中逐筆檢視解析結果與問題項目，並支援資料匯出／匯入以便後續校對與保存",
        "upload_label": "請上傳 Word 或 PDF 檔案",
        "show_imported": "📥 顯示已匯入的資料",
        
        # 側邊欄
        "data_manage": "💾 資料管理",
        "current_status": "📊 當前暫存狀態",
        "in_text_count": "內文引用數量",
        "ref_count": "參考文獻數量",
        "clear_data": "🗑️ 清空資料",
        "clear_btn": "清空所有暫存",
        "clear_success": "已清空所有暫存資料",
        "view_json": "🔍 查看完整暫存資料（JSON 格式）",
        "lang_settings": "### 🌐 語言設定 / Language",
        "lang_select": "選擇語言 / Select Language",

        # File Upload / Analysis
        "file_processing": "📄 處理檔案：",
        "reading_file": "正在讀取檔案...",
        "unsupported_file": "不支援的檔案格式",
        "read_success": "✅ 成功讀取 {count} 個段落",
        "citation_analysis": "🔍 內文引用分析",
        "no_content": "無內文段落可供分析",
        "total_citations": "內文引用總數",
        "apa_citations": "「APA 格式」引用",
        "ieee_citations": "「IEEE 格式」引用",
        "ref_parsing": "📖 參考文獻詳細解析與轉換",
        "no_ref_section": "未找到參考文獻區段",
        "detect_ieee": "💡 偵測到 IEEE 編號格式",
        "detect_apa": "💡 偵測到 APA 格式",
        "parse_success": "成功解析出 {count} 筆參考文獻",
        "total_refs": "參考文獻總數",
        "apa_refs_count": "「APA」格式",
        "ieee_refs_count": "「IEEE」格式",
        "ieee_ref_header": "### 📖 IEEE 格式參考文獻",
        "no_ieee_refs": "無 IEEE 格式參考文獻",
        "apa_ref_header": "### 📚 APA 與其他格式參考文獻",
        "no_apa_refs": "無 APA 格式參考文獻",

        # Components Keys
        "authors": "👥 作者",
        "title": "📝 標題",
        "book_title": "📚 書名",
        "proceedings": "📄 論文集名稱",
        "editors": "✍️ 編輯",
        "conf_name": "會議名稱",
        "journal_name": "期刊名稱",
        "publisher": "出版社",
        "source": "來源出處",
        "volume": "📊 卷期",
        "edition": "📖 版次",
        "article_num": "📄 文章編號",
        "pages": "📄 頁碼",
        "date": "📅 時間",
        "doc_type": "📂 文件類型",
        "doi": "🔍 DOI",
        "url": "🌐 URL",
        "convert_fmt": "**🛠️ 格式轉換**",
        "to_apa": "轉 APA",
        "to_ieee": "轉 IEEE",
        "to_num": "轉編號",
        "orig_text": "📍 原始參考文獻文字",
        "in_text_citation_list": "📋 查看所有內文引用",
        "no_in_text_citation": "未找到任何內文引用",
        "ref_num": "參考編號",
        "author_label": "作者",
        "year_label": "年份",
        "type_label": "類型",
        "no_title": "未提供標題",
        # 交叉比對 & 結果
        "comparison_title": "🚀 交叉比對分析",
        "manual_recompare": "手動重新比對",
        "compare_success": "✅ 比對完成！",
        "compare_fail_msg": "❌ 資料不足，無法比對。請確認是否已成功解析內文引用與參考文獻。",
        "report_title": "📊 比對結果報告",
        
        # Tabs
        "tab_missing": "❌ 遺漏的參考文獻 ({count})",
        "tab_unused": "⚠️ 未使用的參考文獻 ({count})",
        "tab_year_error": "📅 疑似年份錯誤 ({count})",
        
        # Missing Tab
        "missing_desc": "💡 說明：這些引用出現在內文中，但在參考文獻列表裡找不到對應項目。",
        "missing_success": "✅ 太棒了！所有內文引用都在參考文獻列表中找到了。",
        "fmt_label": "格式",
        
        # Unused Tab
        "unused_desc": "💡 說明：這些文獻列在參考文獻列表中，但在內文中從未被引用過。",
        "unused_success": "✅ 太棒了！所有參考文獻都在內文中被有效引用。",
        "unknown_ref": "未知文獻",
        
        # Year Error Tab
        "year_error_desc": "💡 說明：這些文獻的作者匹配，但年份不一致。",
        "year_error_success": "✅ 沒有發現年份錯誤。",
        "year_error_expander": "⚠️ 疑似年份引用錯誤",
        "citation_in_text": "文中引用的是",
        
        # Export Section
        "export_title": "📥 匯出比對結果",
        "download_json": "⬇️ 下載 JSON(遺漏 / 未使用 / 年份錯誤)",
        "download_csv": "⬇️ 下載 CSV(遺漏 / 未使用 / 年份錯誤)",
        "csv_header_type": "類型",
        "csv_header_original": "原始文字",
        "csv_header_format": "格式",
        "csv_header_ref_num": "編號",
        "csv_header_author": "作者",
        "csv_header_year": "年份",
        "csv_header_detail": "錯誤詳情",
        "err_detail_format": "內文:{cited}→正確:{correct}"
    },
    "en": {
        # App Interface
        "page_title": "📚 Academic Citation Checker",
        "features_title": "### ✨ Features",
        "feature_1": "1. ✅ **Reference Integrity Check**: Cross-check Reference List vs. In-Text Citations to find missing or unused references.",
        "feature_2": "2. ✅ **Citation Consistency Check**: Verify if authors, years, or numbers in citations match the reference list correctly.",
        "feature_3": "3. ✅ **Mixed Language & Format Detection**: Smartly detect APA / IEEE / Chinese Numbered formats and support mixed English/Chinese documents.",
        "feature_4": "4. ✅ **Deep Parsing & Conversion**: Extract Author, Year, Title, Journal/Conference, Pages, DOI, URL, and support APA ⇄ IEEE conversions.",
        "feature_5": "5. ✅ **Interactive Report & Export**: Inspect parsing results item-by-item and export/import data for further review.",
        "upload_label": "Upload Word or PDF file",
        "show_imported": "📥 Show Imported Data",
        
        # Sidebar
        "data_manage": "💾 Data Management",
        "current_status": "📊 Current Status",
        "in_text_count": "In-Text Citations",
        "ref_count": "References",
        "clear_data": "🗑️ Clear Data",
        "clear_btn": "Clear All Data",
        "clear_success": "All temporary data cleared",
        "view_json": "🔍 View Raw Data (JSON)",
        "lang_settings": "### 🌐 Language Settings / 語言設定",
        "lang_select": "Select Language / 選擇語言",

        # File Upload / Analysis
        "file_processing": "📄 Processing File: ",
        "reading_file": "Reading file...",
        "unsupported_file": "Unsupported file format",
        "read_success": "✅ Successfully read {count} paragraphs",
        "citation_analysis": "🔍 In-Text Citation Analysis",
        "no_content": "No content paragraphs found for analysis",
        "total_citations": "Total Citations",
        "apa_citations": "APA Citations",
        "ieee_citations": "IEEE Citations",
        "ref_parsing": "📖 Reference Parsing & Conversion",
        "no_ref_section": "Reference section not found",
        "detect_ieee": "💡 Detected IEEE Numbered Format",
        "detect_apa": "💡 Detected APA Format",
        "parse_success": "Successfully parsed {count} references",
        "total_refs": "Total References",
        "apa_refs_count": "APA Format",
        "ieee_refs_count": "IEEE Format",
        "ieee_ref_header": "### 📖 IEEE Format References",
        "no_ieee_refs": "No IEEE format references found",
        "apa_ref_header": "### 📚 APA & Other Format References",
        "no_apa_refs": "No APA format references found",

        # Components Keys
        "authors": "👥 Authors",
        "title": "📝 Title",
        "book_title": "📚 Book Title",
        "proceedings": "📄 Proceedings",
        "editors": "✍️ Editors",
        "conf_name": "Conference",
        "journal_name": "Journal",
        "publisher": "Publisher",
        "source": "Source",
        "volume": "📊 Vol/Issue",
        "edition": "📖 Edition",
        "article_num": "📄 Article No.",
        "pages": "📄 Pages",
        "date": "📅 Date",
        "doc_type": "📂 Document Type",
        "doi": "🔍 DOI",
        "url": "🌐 URL",
        "convert_fmt": "**🛠️ Format Conversion**",
        "to_apa": "To APA",
        "to_ieee": "To IEEE",
        "to_num": "To Numbered",
        "orig_text": "📍 Original Reference Text",
        "in_text_citation_list": "📋 View All In-Text Citations",
        "no_in_text_citation": "No in-text citations found",
        "ref_num": "Ref Number",
        "author_label": "Author",
        "year_label": "Year",
        "type_label": "Type",
        "no_title": "No Title Provided",
        # Comparison & Results
        "comparison_title": "🚀 Cross-Check Analysis",
        "manual_recompare": "Re-run Comparison Manually",
        "compare_success": "✅ Comparison Complete!",
        "compare_fail_msg": "❌ Insufficient data. Please ensure citations and references are parsed successfully.",
        "report_title": "📊 Comparison Report",
        
        # Tabs
        "tab_missing": "❌ Missing References ({count})",
        "tab_unused": "⚠️ Unused References ({count})",
        "tab_year_error": "📅 Year Mismatches ({count})",
        
        # Missing Tab
        "missing_desc": "💡 Note: These citations appear in the text but cannot be found in the Reference List.",
        "missing_success": "✅ Great! All in-text citations are found in the reference list.",
        "fmt_label": "Format",
        
        # Unused Tab
        "unused_desc": "💡 Note: These references are listed but never cited in the text.",
        "unused_success": "✅ Great! All references are effectively cited in the text.",
        "unknown_ref": "Unknown Reference",
        
        # Year Error Tab
        "year_error_desc": "💡 Note: Authors match, but the publication year is inconsistent.",
        "year_error_success": "✅ No year mismatches found.",
        "year_error_expander": "⚠️ Potential Year Mismatch",
        "citation_in_text": "Cited in text as",
        
        # Export Section
        "export_title": "📥 Export Results",
        "download_json": "⬇️ Download JSON (Missing / Unused / Errors)",
        "download_csv": "⬇️ Download CSV (Missing / Unused / Errors)",
        "csv_header_type": "Type",
        "csv_header_original": "Original Text",
        "csv_header_format": "Format",
        "csv_header_ref_num": "Ref Num",
        "csv_header_author": "Author",
        "csv_header_year": "Year",
        "csv_header_detail": "Error Detail",
        "err_detail_format": "In-Text:{cited}→Correct:{correct}"
    }
}

def get_text(key, **kwargs):
    """取得對應語言的文字，支援格式化字串"""
    # 這裡要小心 st.session_state 在某些極端 import 情況下可能還沒初始化
    lang = st.session_state.get('language', 'zh')
    text = TRANSLATIONS[lang].get(key, key)
    if kwargs:
        return text.format(**kwargs)
    return text
