import streamlit as st

# 引入模組
from storage import init_session_state
from utils.section_detector import classify_document_sections
from ui.file_upload import (
    handle_file_upload,
    display_citation_analysis,
    display_reference_parsing
)
from ui.comparison_ui import (
    # display_comparison_button,
    display_comparison_results,
    run_comparison 
)
from citation.in_text_extractor import extract_in_text_citations
from utils.i18n import get_text  # [新增] 匯入翻譯函式

# ==================== 頁面設定 ====================
st.set_page_config(page_title="Citation Checker", layout="wide")

# 初始化 session state
init_session_state()

# [新增] 語言設定初始化
if 'language' not in st.session_state:
    st.session_state.language = 'zh'

# ==================== 側邊欄：語言與資料管理 ====================
with st.sidebar:
    # 1. 語言設定 (最優先顯示)
    st.markdown(get_text("lang_settings"))
    lang_choice = st.radio(
        get_text("lang_select"),
        options=["繁體中文", "English"],
        index=0 if st.session_state.language == 'zh' else 1,
        key="language_radio"
    )
    # 更新 session state
    st.session_state.language = 'zh' if lang_choice == "繁體中文" else 'en'
    
    st.markdown("---")

# ==================== 主區域 ====================
st.title(get_text("page_title"))

# 功能特色說明 (使用 get_text)
st.markdown(get_text("features_title"))
st.markdown(get_text("feature_1"))
st.markdown(get_text("feature_2"))
st.markdown(get_text("feature_3"))
st.markdown(get_text("feature_4"))
st.markdown(get_text("feature_5"))

st.markdown("---")

# ==================== 主區域：檔案上傳 ====================
uploaded_file = st.file_uploader(get_text("upload_label"), type=["docx", "pdf"])

if not uploaded_file and (st.session_state.in_text_citations or st.session_state.reference_list):
    st.info(get_text("show_imported"))

elif uploaded_file:
    # 檢查是否為新檔案
    current_file_id = f"{uploaded_file.name}_{uploaded_file.size}"
    
    # [關鍵修改] 判斷是否為新檔案，如果是，重置狀態並準備重新分析
    if st.session_state.get('last_file_id') != current_file_id:
        st.session_state.in_text_citations = []
        st.session_state.reference_list = []
        st.session_state.missing_refs = []
        st.session_state.unused_refs = []
        st.session_state.comparison_done = False # 重置比對狀態
        st.session_state.last_file_id = current_file_id
    
    # 讀取檔案
    all_paragraphs = handle_file_upload(uploaded_file)

    # 分離內文與參考文獻
    content_paras, ref_paras, ref_start_idx, ref_keyword = classify_document_sections(all_paragraphs)

    # 1. 先解析參考文獻（總覽統計）
    display_reference_parsing(ref_paras)

    # 2. 分析內文引用（但先不顯示，只解析存入 session）
    reference_list = st.session_state.get('reference_list', [])
    in_text_citations = extract_in_text_citations(content_paras, reference_list)
    # 轉換為可序列化格式並存入 session
    serializable_citations = []
    for cite in in_text_citations:
        cite_dict = {
            'author': cite.get('author'),
            'co_author': cite.get('co_author'),
            'year': cite.get('year'),
            'ref_number': cite.get('ref_number'),
            'all_numbers': cite.get('all_numbers'),
            'original': cite.get('original'),
            'normalized': cite.get('normalized'),
            'position': cite.get('position'),
            'type': cite.get('type'),
            'format': cite.get('format'),
            'matched_ref_index': cite.get('matched_ref_index')
        }
        serializable_citations.append(cite_dict)
    st.session_state.in_text_citations = serializable_citations

    # 3. 自動執行交叉比對
    if st.session_state.in_text_citations and st.session_state.reference_list:
        if st.session_state.get("block_compare", False):
            st.info("⛔ 因參考文獻作者/年份為必要比對資訊且未能可靠解析，已暫停交叉比對（仍可查看逐筆解析結果）。")
        else:
            if not st.session_state.get('comparison_done', False):
                with st.spinner("正在自動進行交叉比對..."):
                    run_comparison()

    # 4. 優先顯示：交叉比對結果
    if st.session_state.get('comparison_done', False):
        display_comparison_results()
        st.markdown("---")

    # 5. 顯示內文引用分析（使用已存在 session 中的資料）
    display_citation_analysis(content_paras)

    # 6. 參考文獻逐筆解析結果
    if st.session_state.reference_list:
        st.subheader("📌 參考文獻逐筆解析結果")
        from ui.components import display_reference_with_details
        
        parsed_refs = st.session_state.reference_list
        format_type = st.session_state.get("format_type", "APA")
        
        for idx, ref in enumerate(parsed_refs, 1):
            display_reference_with_details(ref, idx, format_type=format_type)
        
        st.markdown("---")

    # 7. 匯出比對結果
    if st.session_state.get('comparison_done', False):
        from ui.comparison_ui import display_export_section
        display_export_section()