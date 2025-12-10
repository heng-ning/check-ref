"""
學術文獻引用檢查系統 - 主程式
"""

import streamlit as st
import re
from datetime import datetime

# 從各模組引入函式
from common_utils import (
    extract_paragraphs_from_docx,
    extract_paragraphs_from_pdf,
    classify_document_sections,
    extract_in_text_citations
)

from ieee_module import (
    merge_references_ieee_strict,
    convert_en_ieee_to_apa
)

from apa_module import (
    merge_references_unified,
    process_single_reference,
    convert_en_apa_to_ieee,
    convert_zh_apa_to_num,
    convert_zh_num_to_apa,
    format_pages_display
)

from checker import check_references

from storage import (
    init_session_state,
    save_to_session,
    export_to_json,
    import_from_json,
    add_verified_reference
)


# ==================== 頁面設定 ====================

st.set_page_config(page_title="文獻檢查系統 V3", layout="wide")

# 初始化 session state
init_session_state()


# ==================== 標題區 ====================

st.title("📚 學術文獻引用檢查系統")

st.markdown("""
### ✨ 功能特色
1. ✅ **參考文獻檢查**：檢查文獻是否都被引用
2. ✅ **內文引用檢查**：檢查內文中的引用是否都對應參考文獻
3. ✅ **中英文辨識 & 格式轉換**：自動區分中英文、APA/IEEE 互轉
4. ✅ **深度欄位解析**：精準拆解作者、年份、篇名、DOI
5. ✅ **生成檢查報表**：輸出完整報告            
""")

st.markdown("---")


# ==================== 側邊欄：資料管理 ====================

with st.sidebar:
    st.header("💾 資料管理")
    
    # 顯示當前暫存狀態
    st.subheader("📊 當前暫存狀態")
    st.metric("內文引用數量", len(st.session_state.in_text_citations))
    st.metric("參考文獻數量", len(st.session_state.reference_list))
    st.metric("已驗證文獻", len(st.session_state.verified_references))
    
    st.markdown("---")
    
    # 匯出功能
    st.subheader("📤 匯出資料")
    if st.button("匯出為 JSON", use_container_width=True):
        json_data = export_to_json()
        st.download_button(
            label="📥 下載 JSON 檔案",
            data=json_data,
            file_name=f"citation_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True
        )
    
    # 匯入功能
    st.subheader("📥 匯入資料")
    uploaded_json = st.file_uploader("上傳 JSON 檔案", type=['json'])
    if uploaded_json:
        json_str = uploaded_json.read().decode('utf-8')
        success, message = import_from_json(json_str)
        if success:
            st.session_state.json_imported = True
            st.success(message)
        else:
            st.error(message)
    
    # 清除匯入標記
    if not uploaded_json and 'json_imported' in st.session_state:
        del st.session_state.json_imported
    
    # 清空資料
    st.markdown("---")
    st.subheader("🗑️ 清空資料")
    if st.button("清空所有暫存", type="secondary", use_container_width=True):
        st.session_state.in_text_citations = []
        st.session_state.reference_list = []
        st.session_state.verified_references = []
        st.success("已清空所有暫存資料")
        st.rerun()

def display_reference_with_details(ref, index, format_type='IEEE'):
    """ 統一顯示參考文獻的詳細資訊 """
    title_text = ref.get('title', '未提供標題')
    ref_num = ref.get('ref_number', str(index))
    
    # 根據來源類型決定圖示
    stype = ref.get('source_type') or ''
    doc_type = ref.get('document_type') or ''
    lang = ref.get('lang', 'EN')
    
    # 智慧圖示選擇
    if 'Conference' in stype or 'Conference' in doc_type:
        icon = '🗣️'
    elif 'Journal' in stype or 'Journal' in doc_type or ref.get('source'):
        icon = '📚'
    elif 'Thesis' in stype or 'Thesis' in doc_type:
        icon = '🎓'
    elif 'Website' in stype or ref.get('url'):
        icon = '🌐'
    elif 'Book' in stype or 'Book' in doc_type or ref.get('book_title'):
        icon = '📖'
    elif 'Patent' in stype:
        icon = '💡'
    elif 'Report' in stype:
        icon = '📄'
    else:
        icon = '📄'
    
    with st.expander(f"{icon} [{ref_num}] {title_text}", expanded=False):
        c_info, c_action = st.columns([3, 1])
        
        with c_info:
            # 作者
            authors_data = ref.get('authors')
            if authors_data:
                st.markdown(f"**👥 作者**")
                # IEEE 格式才使用 parsed_authors（名 姓）
                if format_type == 'IEEE' and ref.get('parsed_authors'):
                    auth_list = [f"{a.get('first', '')} {a.get('last', '')}".strip() for a in ref['parsed_authors']]
                    st.markdown(f"　└─ {', '.join(auth_list)}")
                elif isinstance(authors_data, list):
                    # APA 格式的作者列表
                    if lang == 'ZH':
                        author_display = "、".join(authors_data)
                    else:
                        author_display = ", ".join(authors_data)
                    st.markdown(f"　└─ {author_display}")
                else:
                    # 字串格式作者
                    st.markdown(f"　└─ {authors_data}")
            
            # 標題
            if ref.get('title'):
                st.markdown(f"**📝 標題**")
                st.markdown(f"　└─ {ref['title']}")
            
            # 書名（若為書籍章節）
            if ref.get('book_title'):
                st.markdown(f"**📚 書名**")
                st.markdown(f"　└─ {ref['book_title']}")
            
            # 編輯
            if ref.get('editors'):
                st.markdown(f"**✍️ 編輯**")
                st.markdown(f"　└─ {ref['editors']}")
            
            # 來源（會議、期刊、出版社）
            # 根據格式顯示不同欄位，但保持相同順序
            if format_type == 'IEEE':
                source_show = (ref.get('conference_name') or 
                            ref.get('journal_name') or 
                            ref.get('source'))
            else:  # APA
                source_show = (ref.get('source') or 
                            ref.get('publisher'))

            if source_show:
                if ref.get('conference_name'):
                    label = "會議名稱"
                elif ref.get('journal_name'):
                    label = "期刊名稱"
                elif ref.get('source'):
                    label = "期刊名稱" if format_type == 'IEEE' else "期刊名稱"
                elif ref.get('publisher'):
                    label = "出版社"
                else:
                    label = "來源出處"
                st.markdown(f"**📖 {label}**")
                st.markdown(f"　└─ {source_show}")
            
            # 卷期
            if ref.get('volume') or ref.get('issue'):
                vol_str = f"Vol. {ref['volume']}" if ref.get('volume') else ""
                issue_str = f"No. {ref['issue']}" if ref.get('issue') else ""
                vi_display = ", ".join(filter(None, [vol_str, issue_str]))
                st.markdown(f"**📊 卷期**")
                st.markdown(f"　└─ {vi_display}")
            
            # 頁碼/文章編號
            if ref.get('article_number'):
                st.markdown(f"**📄 文章編號**")
                st.markdown(f"　└─ {ref['article_number']}")
            elif ref.get('pages'):
                formatted_pages = format_pages_display(ref['pages'])
                st.markdown(f"**📄 頁碼**")
                st.markdown(f"　└─ {formatted_pages}")
            
            # 年份與月份
            if ref.get('year'):
                date_str = ref['year']
                if ref.get('month'):
                    date_str = f"{ref['month']} {date_str}"
                st.markdown(f"**📅 年份**")
                st.markdown(f"　└─ {date_str}")
            
            # 文件類型
            if ref.get('document_type'):
                st.markdown(f"**📂 文件類型**")
                st.markdown(f"　└─ {ref['document_type']}")
            
            # 電子資源
            if ref.get('doi'):
                st.markdown(f"**🔍 DOI**")
                st.markdown(f"　└─ [{ref['doi']}](https://doi.org/{ref['doi']})")
            
            if ref.get('url'):
                st.markdown(f"**🌐 URL**")
                st.markdown(f"　└─ [{ref['url']}]({ref['url']})")
            
            # 原文
            st.divider()
            st.caption("📍 原始參考文獻文字")
            st.code(ref['original'], language=None)
        
        with c_action:
            st.markdown("**🛠️ 操作**")
            
            # 根據格式顯示不同的轉換按鈕
            if format_type == 'IEEE':
                if st.button("轉 APA", key=f"ref_to_apa_{index}"):
                    st.code(convert_en_ieee_to_apa(ref), language='text')
            
            elif format_type == 'APA':
                if lang == 'EN':
                    if st.button("轉 IEEE", key=f"ref_to_ieee_{index}"):
                        st.code(convert_en_apa_to_ieee(ref), language='text')
                elif lang == 'ZH':
                    fmt = ref.get('format', '')
                    if 'APA' in fmt:
                        if st.button("轉編號", key=f"ref_to_num_{index}"):
                            st.code(convert_zh_apa_to_num(ref), language='text')
                    elif 'Numbered' in fmt:
                        if st.button("轉 APA", key=f"ref_to_apa_{index}"):
                            st.code(convert_zh_num_to_apa(ref), language='text')

# ==================== 主區域：檔案上傳 ====================

uploaded_file = st.file_uploader("請上傳 Word 或 PDF 檔案", type=["docx", "pdf"])

# 如果有匯入的資料但沒有上傳檔案，顯示匯入的資料
if not uploaded_file and (st.session_state.in_text_citations or st.session_state.reference_list):
    st.info("📥 顯示已匯入的資料")

elif uploaded_file:
    # 清空舊資料
    st.session_state.in_text_citations = []
    st.session_state.reference_list = []
    if 'missing_refs' in st.session_state:
        del st.session_state.missing_refs
    if 'unused_refs' in st.session_state:
        del st.session_state.unused_refs

    file_ext = uploaded_file.name.split(".")[-1].lower()
    
    st.subheader(f"📄 處理檔案：{uploaded_file.name}")
    
    # ==================== 讀取檔案 ====================
    
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
    
    # ==================== 分離內文與參考文獻 ====================
    
    content_paras, ref_paras, ref_start_idx, ref_keyword = classify_document_sections(all_paragraphs)
    
    
    # ==================== 內文引用分析 ====================
    
    st.subheader("🔍 內文引用分析")
    
    if content_paras:
        in_text_citations = extract_in_text_citations(content_paras)
        
        # 轉換為可序列化格式並儲存
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
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border-radius: 12px;
                padding: 24px;
                text-align: center;
                color: white;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            ">
                <div style="font-size: 20px; opacity: 0.9; margin-bottom: 8px;">內文引用總數</div>
                <div style="font-size: 36px; font-weight: bold;">{len(in_text_citations)}</div>
            </div>
            """, unsafe_allow_html=True)
        
        apa_count = sum(1 for c in in_text_citations if c['format'] == 'APA')
        with col2:
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
                border-radius: 12px;
                padding: 24px;
                text-align: center;
                color: white;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            ">
                <div style="font-size: 20px; opacity: 0.9; margin-bottom: 8px;">APA 格式引用</div>
                <div style="font-size: 36px; font-weight: bold;">{apa_count}</div>
            </div>
            """, unsafe_allow_html=True)
        
        ieee_count = sum(1 for c in in_text_citations if c['format'] == 'IEEE')
        with col3:
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #0066cc 0%, #0080ff 100%);
                border-radius: 12px;
                padding: 24px;
                text-align: center;
                color: white;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            ">
                <div style="font-size: 20px; opacity: 0.9; margin-bottom: 8px;">IEEE 格式引用</div>
                <div style="font-size: 36px; font-weight: bold;">{ieee_count}</div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # 展開查看所有引用
        if in_text_citations:
            with st.expander("📋 查看所有內文引用"):
                for i, cite in enumerate(in_text_citations, 1):
                    if cite['format'] == 'APA':
                        co_author_text = f" & {cite['co_author']}" if cite['co_author'] else ""
                        st.markdown(
                            f"{i}. `{cite['original']}` — "
                            f"**[{cite['format']}]** "
                            f"作者：**{cite['author']}{co_author_text}** | "
                            f"年份：**{cite['year']}** | "
                            f"類型：{cite['type']}"
                        )
                    else:
                        st.markdown(
                            f"{i}. `{cite['original']}` — "
                            f"**[{cite['format']}]** "
                            f"參考編號：**{cite['ref_number']}**"
                        )
        else:
            st.info("未找到任何內文引用")
    else:
        st.warning("無內文段落可供分析")
    
    st.markdown("---")
    
    
    # ==================== 參考文獻解析 ====================
    
    if ref_paras:
        st.subheader("📖 參考文獻詳細解析與轉換")
        
        # 自動偵測格式
        is_ieee_mode = False
        sample_count = min(len(ref_paras), 15)
        for i in range(sample_count):
            if re.match(r'^\s*[\[【]\s*\d+\s*[】\]]', ref_paras[i].strip()):
                is_ieee_mode = True
                break
        
        if is_ieee_mode:
            st.info("💡 偵測到 IEEE 編號格式，啟用**嚴格分割模式**")
            merged_refs = merge_references_ieee_strict(ref_paras)
        else:
            st.info("💡 偵測到一般格式 (APA/中文)，啟用**智慧混合模式**")
            merged_refs = merge_references_unified(ref_paras)
        
        # 解析參考文獻
        parsed_refs = [process_single_reference(r) for r in merged_refs]
        st.session_state.reference_list = parsed_refs
        
        st.info(f"成功解析出 {len(parsed_refs)} 筆參考文獻")
        
        # 統計卡片
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border-radius: 12px;
                padding: 20px;
                text-align: center;
                color: white;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            ">
                <div style="font-size: 18px; opacity: 0.9; margin-bottom: 6px;">參考文獻總數</div>
                <div style="font-size: 28px; font-weight: bold;">{len(parsed_refs)}</div>
            </div>
            """, unsafe_allow_html=True)
        
        apa_refs_count = sum(1 for r in parsed_refs if 'APA' in r.get('format', ''))
        with col2:
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
                border-radius: 12px;
                padding: 20px;
                text-align: center;
                color: white;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            ">
                <div style="font-size: 18px; opacity: 0.9; margin-bottom: 6px;">APA 格式</div>
                <div style="font-size: 28px; font-weight: bold;">{apa_refs_count}</div>
            </div>
            """, unsafe_allow_html=True)
        
        ieee_refs_count = sum(1 for r in parsed_refs if 'IEEE' in r.get('format', ''))
        with col3:
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #0066cc 0%, #0080ff 100%);
                border-radius: 12px;
                padding: 20px;
                text-align: center;
                color: white;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            ">
                <div style="font-size: 18px; opacity: 0.9; margin-bottom: 6px;">IEEE 格式</div>
                <div style="font-size: 28px; font-weight: bold;">{ieee_refs_count}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #ff7675 0%, #ff9a3d 100%);
                border-radius: 12px;
                padding: 20px;
                text-align: center;
                color: white;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            ">
                <div style="font-size: 18px; opacity: 0.9; margin-bottom: 6px;">其他/混合</div>
                <div style="font-size: 28px; font-weight: bold;">0</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col5:
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #95de64 0%, #b3e5fc 100%);
                border-radius: 12px;
                padding: 20px;
                text-align: center;
                color: #333;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            ">
                <div style="font-size: 18px; opacity: 0.9; margin-bottom: 6px;">未知格式</div>
                <div style="font-size: 28px; font-weight: bold;">0</div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # IEEE 參考文獻展示
        st.markdown("### 📖 IEEE 格式參考文獻")
        ieee_list = [ref for ref in parsed_refs if 'IEEE' in ref.get('format', '')]
        if ieee_list:
            for i, ref in enumerate(ieee_list, 1):
                display_reference_with_details(ref, i, format_type='IEEE')
        else:
            st.info("無 IEEE 格式參考文獻")

        st.markdown("---")

        # APA 參考文獻展示
        st.markdown("### 📚 APA 與其他格式參考文獻")
        apa_list = [ref for ref in parsed_refs if 'APA' in ref.get('format', '') or 'Numbered' in ref.get('format', '')]
        if apa_list:
            for i, ref in enumerate(apa_list, 1):
                display_reference_with_details(ref, i , format_type='APA') 
        else:
            st.info("無 APA 格式參考文獻")

st.markdown("---")


# ==================== 交叉比對分析 ====================

st.header("🚀 交叉比對分析")
st.info("👆 請確認上方解析結果無誤後，點擊下方按鈕開始檢查。")

if st.button("開始交叉比對", type="primary", use_container_width=True):
    if not st.session_state.in_text_citations or not st.session_state.reference_list:
        st.error("❌ 資料不足，無法比對。請確認是否已成功解析內文引用與參考文獻。")
    else:
        with st.spinner("正在進行雙向交叉比對..."):
            missing, unused = check_references(
                st.session_state.in_text_citations,
                st.session_state.reference_list
            )
            
            st.session_state.missing_refs = missing
            st.session_state.unused_refs = unused
            
            st.success("✅ 比對完成！")


# ==================== 顯示比對結果 ====================

if 'missing_refs' in st.session_state and 'unused_refs' in st.session_state:
    st.subheader("📊 比對結果報告")
    
    tab1, tab2 = st.tabs([
        f"❌ 遺漏的參考文獻 ({len(st.session_state.missing_refs)})", 
        f"⚠️ 未使用的參考文獻 ({len(st.session_state.unused_refs)})"
    ])
    
    with tab1:
        st.caption("💡 說明：這些引用出現在內文中，但在參考文獻列表裡找不到對應項目。")

        if not st.session_state.missing_refs:
            st.success("太棒了！所有內文引用都在參考文獻列表中找到了。")
        else:
            for i, item in enumerate(st.session_state.missing_refs, 1):
                if item.get('error_type') == 'year_mismatch':
                    st.warning(
                        f"{i}. **{item['original']}** (格式: {item['format']})\n\n"
                        f"⚠️ **疑似年份引用錯誤**：系統在參考文獻中找到了同名作者，"
                        f"但年份似乎是 **{item.get('year_hint', '不同年份')}**，而非內文寫的 **{item.get('year')}**。",
                        icon="📅"
                    )
                else:
                    st.error(f"{i}. **{item['original']}** (格式: {item['format']})", icon="🚨")

    with tab2:
        st.caption("💡 說明：這些文獻列在參考文獻列表中，但在內文中從未被引用過。")
        if not st.session_state.unused_refs:
            st.success("太棒了！所有參考文獻都在內文中被有效引用。")
        else:
            for i, item in enumerate(st.session_state.unused_refs, 1):
                st.warning(f"{i}. **{item['original']}**", icon="🗑️")


# ==================== 查看暫存資料 ====================

if st.session_state.in_text_citations or st.session_state.reference_list:
    with st.expander("🔍 查看完整暫存資料（JSON 格式）"):
        st.json({
            "in_text_citations": st.session_state.in_text_citations,
            "reference_list": st.session_state.reference_list,
            "verified_references": st.session_state.verified_references
        })