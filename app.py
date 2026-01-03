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
    display_comparison_button,
    display_comparison_results
)
from citation.in_text_extractor import extract_in_text_citations 
# ==================== 頁面設定 ====================
st.set_page_config(page_title="文獻檢查系統", layout="wide")

# 初始化 session state
init_session_state()

# ==================== 標題區 ====================
st.title("📚 學術文獻引用檢查系統")

st.markdown("""
### ✨ 功能特色
1. ✅ **參考文獻完整性檢查**：比對「參考文獻列表」與「內文引用」，找出遺漏引用與未使用文獻。
2. ✅ **內文引用一致性檢查**：檢查內文中的作者、年份或編號是否都能正確對應到參考文獻。
3. ✅ **中英混合與格式自動辨識**：智慧偵測 APA / IEEE / 中文數字編號等格式，並支援中英文文獻混排。
4. ✅ **深度欄位解析與格式轉換**：精準拆解作者、年份、篇名、期刊／會議名稱、頁碼、DOI、URL，並提供 APA ⇄ IEEE、自編號 ⇄ APA 等互轉。
5. ✅ **互動式檢查報表與匯出**：在介面中逐筆檢視解析結果與問題項目，並支援資料匯出／匯入以便後續校對與保存         
""")

st.markdown("---")

# ==================== 側邊欄：資料管理 ====================
with st.sidebar:
    st.header("💾 資料管理")
    
    st.subheader("📊 當前暫存狀態")
    st.metric("內文引用數量", len(st.session_state.in_text_citations))
    st.metric("參考文獻數量", len(st.session_state.reference_list))
    st.metric("已驗證文獻", len(st.session_state.verified_references))
    
    st.markdown("---")
    st.subheader("🗑️ 清空資料")
    if st.button("清空所有暫存", type="secondary", use_container_width=True):
        st.session_state.in_text_citations = []
        st.session_state.reference_list = []
        st.session_state.verified_references = []
        st.success("已清空所有暫存資料")
        st.rerun()

# ==================== 主區域：檔案上傳 ====================
uploaded_file = st.file_uploader("請上傳 Word 或 PDF 檔案", type=["docx", "pdf"])

if not uploaded_file and (st.session_state.in_text_citations or st.session_state.reference_list):
    st.info("📥 顯示已匯入的資料")

elif uploaded_file:
    # 檢查是否為新檔案
    current_file_id = f"{uploaded_file.name}_{uploaded_file.size}"
    
    if st.session_state.get('last_file_id') != current_file_id:
        st.session_state.in_text_citations = []
        st.session_state.reference_list = []
        st.session_state.missing_refs = []
        st.session_state.unused_refs = []
        st.session_state.comparison_done = False
        st.session_state.last_file_id = current_file_id
    
    # 讀取檔案
    all_paragraphs = handle_file_upload(uploaded_file)
    
    # 分離內文與參考文獻
    content_paras, ref_paras, ref_start_idx, ref_keyword = classify_document_sections(all_paragraphs)
    
    # 內文引用分析
    display_citation_analysis(content_paras)
    
    # 參考文獻解析
    display_reference_parsing(ref_paras)

st.markdown("---")

# ==================== 交叉比對分析 ====================
display_comparison_button()

if st.session_state.get('comparison_done', False):
    display_comparison_results()

# ==================== 查看暫存資料 ====================
if st.session_state.in_text_citations or st.session_state.reference_list:
    with st.expander("🔍 查看完整暫存資料（JSON 格式）"):
        st.json({
            "in_text_citations": st.session_state.in_text_citations,
            "reference_list": st.session_state.reference_list,
            "verified_references": st.session_state.verified_references
        })