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

def save_to_session(in_text_citations, reference_list):
    """將資料儲存到 session state"""
    st.session_state.in_text_citations = in_text_citations
    st.session_state.reference_list = reference_list

def export_to_json():
    """匯出為 JSON 格式: 將三個清單打包成一個 JSON 物件"""
    data = {
        "export_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "in_text_citations": st.session_state.in_text_citations,
        "reference_list": st.session_state.reference_list,
        "verified_references": st.session_state.verified_references
    }

    # ensure_ascii=False：保留中文字元, indent=2：格式化輸出，方便閱讀
    return json.dumps(data, ensure_ascii=False, indent=2)

def import_from_json(json_str):
    """從 JSON 匯入資料"""
    try:
        data = json.loads(json_str)
        st.session_state.in_text_citations = data.get("in_text_citations", [])
        st.session_state.reference_list = data.get("reference_list", [])
        st.session_state.verified_references = data.get("verified_references", [])
        return True, "資料匯入成功！"
    except Exception as e:
        return False, f"匯入失敗：{str(e)}"

def add_verified_reference(ref_data):
    """新增已驗證的文獻資料"""
    if 'verified_references' not in st.session_state:
        st.session_state.verified_references = []
    st.session_state.verified_references.append(ref_data)

# 引入：
import streamlit as st
import json
from datetime import datetime