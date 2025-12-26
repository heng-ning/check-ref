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
    if 'missing_refs' not in st.session_state:
        st.session_state.missing_refs = []
    if 'unused_refs' not in st.session_state:
        st.session_state.unused_refs = []
    if 'comparison_done' not in st.session_state:
        st.session_state.comparison_done = False

    # 只有在真正換檔案（檔名或大小改變）時才會清空比對結果
    if 'last_file_id' not in st.session_state:
        st.session_state.last_file_id = None

# 引入：
import streamlit as st
import json
from datetime import datetime