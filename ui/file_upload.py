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
    render_stat_card,
    render_citation_list
)

def handle_file_upload(uploaded_file):
    """
    處理檔案上傳與初始讀取
    
    Returns:
        all_paragraphs: 所有段落列表
    """
    file_ext = uploaded_file.name.split(".")[-1].lower()
    
    st.subheader(f"📄 處理檔案：{uploaded_file.name}")
    
    with st.spinner("正在讀取檔案..."):
        if file_ext == "docx":
            all_paragraphs = extract_paragraphs_from_docx(uploaded_file)
        elif file_ext == "pdf":
            all_paragraphs = extract_paragraphs_from_pdf(uploaded_file)
        else:
            st.error("不支援的檔案格式")
            st.stop()
    
    st.success(f"✅ 成功讀取 {len(all_paragraphs)} 個段落")
    st.markdown("---")
    
    return all_paragraphs

def display_citation_analysis(content_paras):
    """
    顯示內文引用分析結果
    
    Returns:
        in_text_citations: 提取的內文引用列表
    """
    st.subheader("🔍 內文引用分析")
    
    if not content_paras:
        st.warning("無內文段落可供分析")
        return []
    
    in_text_citations = extract_in_text_citations(content_paras)
    
    # 轉換為可序列化格式
    serializable_citations = []
    for cite in in_text_citations:
        cite_dict = {
            'author': cite.get('author'),
            'co_author': cite.get('co_author'),
            'year': cite.get('year'),
            'ref_number': cite.get('ref_number'),
            'original': cite.get('original'),
            'normalized': cite.get('normalized'),
            'position': cite.get('position'),
            'type': cite.get('type'),
            'format': cite.get('format')
        }
        serializable_citations.append(cite_dict)
    
    st.session_state.in_text_citations = serializable_citations
    
    # 統計卡片
    apa_count = sum(1 for c in in_text_citations if c['format'] == 'APA')
    ieee_count = sum(1 for c in in_text_citations if c['format'] == 'IEEE')
    
    col1, col2, col3 = st.columns([2, 4, 4])
    
    with col1:
        render_stat_card("內文引用總數", len(in_text_citations), "primary")
    
    with col2:
        render_stat_card("「APA 格式」引用", apa_count, "secondary")
    
    with col3:
        render_stat_card("「IEEE 格式」引用", ieee_count, "secondary")
    
    st.markdown("---")
    
    # 顯示引用列表
    render_citation_list(in_text_citations)
    
    st.markdown("---")
    
    return in_text_citations

def display_reference_parsing(ref_paras):
    """
    顯示參考文獻解析結果
    
    Returns:
        parsed_refs: 解析後的參考文獻列表
    """
    if not ref_paras:
        st.warning("未找到參考文獻區段")
        return []
    
    st.subheader("📖 參考文獻詳細解析與轉換")
    
    # 自動偵測格式
    is_ieee_mode = False
    sample_count = min(len(ref_paras), 15)
    for i in range(sample_count):
        if re.match(r'^\s*[\[【]\s*\d+\s*[】\]]', ref_paras[i].strip()):
            is_ieee_mode = True
            break
    
    if is_ieee_mode:
        st.info("💡 偵測到 IEEE 編號格式")
        merged_refs = merge_references_ieee_strict(ref_paras)
    else:
        st.info("💡 偵測到 APA 格式")
        merged_refs = merge_references_unified(ref_paras)
    
    # 解析參考文獻
    parsed_refs = [process_single_reference(r) for r in merged_refs]
    st.session_state.reference_list = parsed_refs
    
    st.info(f"成功解析出 {len(parsed_refs)} 筆參考文獻")
    
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
        render_stat_card("參考文獻總數", len(parsed_refs), "primary")
    
    with col2:
        render_stat_card("「APA」格式", len(apa_refs), "secondary")
    
    with col3:
        render_stat_card("「IEEE」格式", len(ieee_refs), "secondary")
    
    st.markdown("---")
    
    # 顯示 IEEE 參考文獻
    st.markdown("### 📖 IEEE 格式參考文獻")
    if ieee_refs:
        for i, ref in enumerate(ieee_refs, 1):
            display_reference_with_details(ref, i, format_type='IEEE')
    else:
        st.info("無 IEEE 格式參考文獻")
    
    st.markdown("---")
    
    # 顯示 APA 參考文獻
    st.markdown("### 📚 APA 與其他格式參考文獻")
    if apa_refs:
        for i, ref in enumerate(apa_refs, 1):
            display_reference_with_details(ref, i, format_type='APA')
    else:
        st.info("無 APA 格式參考文獻")
    
    return parsed_refs