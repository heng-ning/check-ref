import streamlit as st
import re
from utils.file_reader import (
    extract_paragraphs_from_docx,
    extract_paragraphs_from_pdf
)
from utils.section_detector import classify_document_sections
from citation.in_text_extractor import extract_in_text_citations
from parsers.ieee.ieee_merger import merge_references_ieee_strict
from parsers.apa.apa_merger import merge_references_unified
from reference_router import process_single_reference
from ui.components import (
    display_reference_with_details,
    render_citation_list
)
from utils.i18n import get_text  # 多語系

# === 折衷版驗證器（必要條件 vs 非必要欄位警告）===
from utils.reference_validator import validate_reference_list_relaxed


def render_stat_card(title, value, color_scheme="primary"):
    border_style = ""

    if color_scheme == "primary":
        bg_color = "#FAF0E6"
        text_color = "#4B2E1E"
        box_shadow = "0 4px 6px rgba(0,0,0,0.3)"
    elif color_scheme == "secondary":
        bg_color = "rgba(242, 231, 203, 0.8)"
        text_color = "#761A0A"
        border_style = "border: 3px solid #844200;"
        box_shadow = "0 4px 6px rgba(0,0,0,0.1)"
    else:
        bg_color = "rgba(242, 231, 203, 0.8)"
        text_color = "#761A0A"
        border_style = "border: 3px solid #844200;"
        box_shadow = "0 4px 6px rgba(0,0,0,0.1)"

    html_content = (
        f'<div style="background: {bg_color}; {border_style} border-radius: 30px; '
        f'padding: 15px; text-align: center; color: {text_color}; '
        f'box-shadow: {box_shadow}; height: 160px; display: flex; '
        f'flex-direction: column; justify-content: center;">'
        f'<div style="font-size: 25px; opacity: 0.9; margin-bottom: 5px; font-weight: bold;">{title}</div>'
        f'<div style="font-size: 45px; font-weight: bold;">{value}</div>'
        f'</div>'
    )
    st.markdown(html_content, unsafe_allow_html=True)


def handle_file_upload(uploaded_file):
    """
    處理檔案上傳與初始讀取
    """
    file_ext = uploaded_file.name.split(".")[-1].lower()
    st.subheader(f"{get_text('file_processing')}{uploaded_file.name}")

    with st.spinner(get_text("reading_file")):
        if file_ext == "docx":
            all_paragraphs = extract_paragraphs_from_docx(uploaded_file)
        elif file_ext == "pdf":
            all_paragraphs = extract_paragraphs_from_pdf(uploaded_file)
        else:
            st.error(get_text("unsupported_file"))
            st.stop()

    st.success(get_text("read_success", count=len(all_paragraphs)))
    st.markdown("---")
    return all_paragraphs

def display_citation_analysis(content_paras):
    """
    顯示內文引用分析結果（使用 session 中已解析的資料）
    """
    # 如果被標記為 block_compare（作者/年份不足），跳過內文引用分析
    if st.session_state.get("block_compare", False):
        return []

    st.subheader(get_text("citation_analysis"))
    
    # 直接從 session 讀取已解析的引用資料
    in_text_citations = st.session_state.get('in_text_citations', [])
    
    if not in_text_citations:
        st.warning(get_text("no_content"))
        return []

    # 統計卡片
    apa_count = sum(1 for c in in_text_citations if c.get('format') == 'APA')
    ieee_count = sum(1 for c in in_text_citations if c.get('format') == 'IEEE')

    col1, col2, col3 = st.columns([2, 4, 4])
    with col1:
        render_stat_card(get_text("total_citations"), len(in_text_citations), "primary")
    with col2:
        render_stat_card(get_text("apa_citations"), apa_count, "secondary")
    with col3:
        render_stat_card(get_text("ieee_citations"), ieee_count, "secondary")

    st.markdown("---")
    render_citation_list(in_text_citations)
    st.markdown("---")

    return in_text_citations

def display_reference_parsing(ref_paras):
    """
    顯示參考文獻解析結果（每一筆都顯示）
    - 作者/年份不足：顯示⛔，並設定 block_compare=True（不比對，但照樣顯示所有筆）
    - 標題/出處不足：顯示⚠️，但允許比對
    """
    if not ref_paras:
        st.warning(get_text("no_ref_section"))
        st.session_state.reference_list = []
        st.session_state["block_compare"] = True
        st.session_state["ref_critical_map"] = {}
        st.session_state["ref_warning_map"] = {}
        return []

    st.subheader(get_text("ref_parsing"))

    # 自動偵測格式（IEEE: [n] / 【n】）
    is_ieee_mode = False
    sample_count = min(len(ref_paras), 15)
    for i in range(sample_count):
        if re.match(r'^\s*[\[【]\s*\d+\s*[】\]]', ref_paras[i].strip()):
            is_ieee_mode = True
            break

    if is_ieee_mode:
        st.info(get_text("detect_ieee"))
        merged_refs = merge_references_ieee_strict(ref_paras)
        format_type = "IEEE"
    else:
        st.info(get_text("detect_apa"))
        merged_refs = merge_references_unified(ref_paras)
        format_type = "APA"

    # 解析參考文獻
    parsed_refs = [process_single_reference(r) for r in merged_refs]

    # ===== 折衷版驗證（必要條件 vs 非必要欄位警告）=====
    critical_ok, critical_results, warning_results = validate_reference_list_relaxed(parsed_refs, format_type)

    # ✅ 永遠寫入 session，確保每一筆都能顯示解析結果
    st.session_state.reference_list = parsed_refs

    # ✅ 建立每筆 index -> messages 的 map，交給每筆顯示用
    critical_map = {r["index"]: r.get("errors", []) for r in critical_results}
    warning_map = {w["index"]: w.get("warnings", []) for w in warning_results}
    st.session_state["ref_critical_map"] = critical_map
    st.session_state["ref_warning_map"] = warning_map

    # ✅ 用這個 gate 交叉比對（作者/年份不足才擋）
    st.session_state["block_compare"] = (not critical_ok)

    # ===== 頁首總結提示（新增：列出是哪幾筆 + 可展開細節）=====
    if not critical_ok:
        st.error(
            f"⛔ 有 {len(critical_results)} 筆參考文獻的必要比對資訊，系統未能可靠取得；"
            f"將暫停交叉比對，但仍會顯示所有文獻的欄位解析結果。"
        )
        st.info("💡 建議修正上述條目後重新上傳，以提升比對準確性。")

        # ✅ 新增：列出筆號
        critical_idxs = [r["index"] for r in critical_results]
        st.markdown("**⛔ 必要條件問題筆號：** " + "、".join(map(str, critical_idxs)))

        # ✅ 新增：展開查看每筆的原文與錯誤原因
        with st.expander("查看必要條件問題明細", expanded=False):
            for r in critical_results:
                idx = r["index"]
                full_original = parsed_refs[idx - 1].get("original", "")

                st.markdown(f"### ⛔ 第 {idx} 筆（{r.get('format_type', format_type)}）")
                st.code(full_original, language="text")
                for msg in r.get("errors", []):
                    st.error(msg)
                st.markdown("---")

    if warning_results:
        st.warning(
            f"⚠️ 有 {len(warning_results)} 筆參考文獻的標題/出處等資訊未能可靠解析（不影響交叉比對）。"
        )

        # ✅ 新增：列出筆號
        warning_idxs = [w["index"] for w in warning_results]
        st.markdown("**⚠️ 非必要欄位提醒筆號：** " + "、".join(map(str, warning_idxs)))

        # ✅ 新增：展開查看每筆的原文與警告原因
        with st.expander("查看非必要欄位提醒明細（標題/出處，不影響比對）", expanded=False):
            for w in warning_results:
                idx = w["index"]
                full_original = parsed_refs[idx - 1].get("original", "")

                st.markdown(f"### ⚠️ 第 {idx} 筆（{w.get('format_type', format_type)}）")
                st.code(full_original, language="text")
                for msg in w.get("warnings", []):
                    st.warning(msg)
                st.markdown("---")

    elif critical_ok:
        st.success("✅ 參考文獻必要條件通過，且欄位解析完整度良好。")
    st.markdown("---")
    # ===== 儲存格式類型到 session，供後續顯示使用 =====
    st.session_state["format_type"] = format_type
    return parsed_refs
