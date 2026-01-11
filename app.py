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

    # 2. 資料管理
    st.header(get_text("data_manage"))
    
    st.subheader(get_text("current_status"))
    st.metric(get_text("in_text_count"), len(st.session_state.in_text_citations))
    st.metric(get_text("ref_count"), len(st.session_state.reference_list))
    
    st.markdown("---")
    st.subheader(get_text("clear_data"))
    if st.button(get_text("clear_btn"), type="secondary", use_container_width=True):
        st.session_state.in_text_citations = []
        st.session_state.reference_list = []
        st.success(get_text("clear_success"))
        st.rerun()

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
    
    # 先解析參考文獻
    display_reference_parsing(ref_paras)

    # 再分析內文引用（使用已解析的參考文獻）
    display_citation_analysis(content_paras)
    
    # 3. [新增] 自動執行交叉比對
    # 只要有解析出資料，且還沒做過比對（或者希望每次重新解析都跑），就自動執行
    if st.session_state.in_text_citations and st.session_state.reference_list:
        if not st.session_state.get('comparison_done', False):
            with st.spinner("正在自動進行交叉比對..."):
                run_comparison()

st.markdown("---")

# ==================== 交叉比對分析結果區 ====================
# [修改] 這裡可以選擇是否還要顯示「手動比對按鈕」。
# 如果您希望完全自動化，可以把 display_comparison_button() 拿掉，
# 或者保留它當作「重新整理」的按鈕。

# 顯示結果 (只要 comparison_done 為 True 就顯示)
if st.session_state.get('comparison_done', False):
    display_comparison_results()
# else:
#     # 如果還沒完成比對 (例如解析失敗)，顯示手動按鈕讓使用者嘗試
#     display_comparison_button()