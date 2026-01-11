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
from utils.i18n import get_text  # [新增] 匯入翻譯函式

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
    # [移除] 這裡的語言選擇器程式碼 (已搬移至 app.py)

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
    顯示內文引用分析結果
    """
    st.subheader(get_text("citation_analysis"))
    
    if not content_paras:
        st.warning(get_text("no_content"))
        return []
    
    # 傳入已解析的參考文獻列表
    reference_list = st.session_state.get('reference_list', [])
    in_text_citations = extract_in_text_citations(content_paras, reference_list)
    
    # 轉換為可序列化格式
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
            'matched_ref_index': cite.get('matched_ref_index')  # 保存匹配到的參考文獻索引
        }
        serializable_citations.append(cite_dict)
    
    st.session_state.in_text_citations = serializable_citations
    
    # 統計卡片
    apa_count = sum(1 for c in in_text_citations if c['format'] == 'APA')
    ieee_count = sum(1 for c in in_text_citations if c['format'] == 'IEEE')
    
    col1, col2, col3 = st.columns([2, 4, 4])
    
    with col1:
        render_stat_card(get_text("total_citations"), len(in_text_citations), "primary")
    
    with col2:
        render_stat_card(get_text("apa_citations"), apa_count, "secondary")
    
    with col3:
        render_stat_card(get_text("ieee_citations"), ieee_count, "secondary")
    
    st.markdown("---")
    
    # 顯示引用列表 (這個組件若還沒多語言化，可能還是會顯示中文)
    render_citation_list(in_text_citations)
    
    st.markdown("---")
    
    return in_text_citations


def display_reference_parsing(ref_paras):
    """
    顯示參考文獻解析結果
    """
    if not ref_paras:
        st.warning(get_text("no_ref_section"))
        return []
    
    st.subheader(get_text("ref_parsing"))
    
    # 自動偵測格式
    is_ieee_mode = False
    sample_count = min(len(ref_paras), 15)
    for i in range(sample_count):
        if re.match(r'^\s*[\[【]\s*\d+\s*[】\]]', ref_paras[i].strip()):
            is_ieee_mode = True
            break
    
    if is_ieee_mode:
        st.info(get_text("detect_ieee"))
        merged_refs = merge_references_ieee_strict(ref_paras)
    else:
        st.info(get_text("detect_apa"))
        merged_refs = merge_references_unified(ref_paras)
    
    # 解析參考文獻
    parsed_refs = [process_single_reference(r) for r in merged_refs]
    st.session_state.reference_list = parsed_refs
    
    st.info(get_text("parse_success", count=len(parsed_refs)))
    
    # 分類統計
    apa_refs = []
    ieee_refs = []
    for r in parsed_refs:
        if r.get('ref_number'):
            ieee_refs.append(r)
        else:
            fmt = str(r.get('format', ''))
            if fmt.startswith('APA'):
                apa_refs.append(r)
            else:
                ieee_refs.append(r)
    
    # 統計卡片
    col1, col2, col3 = st.columns([2, 4, 4])
    
    with col1:
        render_stat_card(get_text("total_refs"), len(parsed_refs), "primary")
    
    with col2:
        render_stat_card(get_text("apa_refs_count"), len(apa_refs), "secondary")
    
    with col3:
        render_stat_card(get_text("ieee_refs_count"), len(ieee_refs), "secondary")
    
    st.markdown("---")
    
    # 顯示 IEEE 參考文獻
    st.markdown(get_text("ieee_ref_header"))
    if ieee_refs:
        for i, ref in enumerate(ieee_refs, 1):
            display_reference_with_details(ref, i, format_type='IEEE')
    else:
        st.info(get_text("no_ieee_refs"))
    
    st.markdown("---")
    
    # 顯示 APA 參考文獻
    st.markdown(get_text("apa_ref_header"))
    if apa_refs:
        for i, ref in enumerate(apa_refs, 1):
            display_reference_with_details(ref, i, format_type='APA')
    else:
        st.info(get_text("no_apa_refs"))
    
    return parsed_refs
