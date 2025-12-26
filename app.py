"""
學術文獻引用檢查系統 - 主程式
"""
from reference_router import process_single_reference
import streamlit as st
import re
from datetime import datetime
import json
import pandas as pd

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
    
    # 顯示當前暫存狀態
    st.subheader("📊 當前暫存狀態")
    st.metric("內文引用數量", len(st.session_state.in_text_citations))
    st.metric("參考文獻數量", len(st.session_state.reference_list))
    st.metric("已驗證文獻", len(st.session_state.verified_references))
    
    # st.markdown("---")
    
    # 匯出功能
    # st.subheader("📤 匯出資料")
    # if st.button("匯出為 JSON", use_container_width=True):
    #     json_data = export_to_json()
    #     st.download_button(
    #         label="📥 下載 JSON 檔案",
    #         data=json_data,
    #         file_name=f"citation_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
    #         mime="application/json",
            
    #         use_container_width=True
    #     )
    
    # # 匯入功能
    # st.subheader("📥 匯入資料")
    # uploaded_json = st.file_uploader("上傳 JSON 檔案", type=['json'])
    # if uploaded_json:
    #     json_str = uploaded_json.read().decode('utf-8')
    #     success, message = import_from_json(json_str)
    #     if success:
    #         st.session_state.json_imported = True
    #         st.success(message)
    #     else:
    #         st.error(message)
    
    # # 清除匯入標記
    # if not uploaded_json and 'json_imported' in st.session_state:
    #     del st.session_state.json_imported
    
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
    lang = ref.get('lang', 'EN')
    
    with st.expander(f"[{ref_num}] {title_text}", expanded=False):
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
            volume_val = ref.get('volume')
            issue_val = ref.get('issue')
            
            # 只有當值不是 None 時才處理
            if volume_val and issue_val:
                # 判斷期號格式
                issue_str = str(issue_val)
                
                # 檢查是否為純數字、數字範圍（1-2、3–4）、或 "1, 2" 格式
                is_numeric_issue = bool(
                    issue_str.isdigit() or 
                    re.match(r'^\d+[\-–—]\d+$', issue_str) or  # 數字範圍
                    re.match(r'^\d+,\s*\d+$', issue_str)       # 逗號分隔的數字
                )
                
                if is_numeric_issue:
                    # 純數字或數字範圍：使用 Vol. X, No. Y 格式
                    vi_display = f"Vol. {volume_val}, No. {issue_str}"
                else:
                    # 包含文字（如 Supplement）：使用 Vol. X(Y) 格式
                    vi_display = f"Vol. {volume_val}({issue_str})"
            elif volume_val:
                vi_display = f"Vol. {volume_val}"
            elif issue_val:
                vi_display = f"No. {issue_val}"
            else:
                vi_display = None
            
            if vi_display:
                st.markdown(f"**📊 卷期**")
                st.markdown(f"　└─ {vi_display}")
        
        # 版次
        if ref.get('edition'):
            st.markdown(f"**📖 版次**")
            st.markdown(f"　└─ {ref['edition']}")

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
            st.markdown(f"**📅 時間**")
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

        col_title, col_button = st.columns([3, 1])
        with col_title:
            st.markdown("**🛠️ 格式轉換**")
    
        with col_button:
            # 根據格式顯示不同的轉換按鈕
            if format_type == 'IEEE':
                button_clicked = st.button("轉 APA", key=f"ref_to_apa_{index}", use_container_width=True)
            elif format_type == 'APA':
                if lang == 'EN':
                    button_clicked = st.button("轉 IEEE", key=f"ref_to_ieee_{index}", use_container_width=True)
                elif lang == 'ZH':
                    fmt = ref.get('format', '')
                    if 'APA' in fmt:
                        button_clicked = st.button("轉編號", key=f"ref_to_num_{index}", use_container_width=True)
                    elif 'Numbered' in fmt:
                        button_clicked = st.button("轉 APA", key=f"ref_to_apa_{index}", use_container_width=True)
                    else:
                        button_clicked = False
                else:
                    button_clicked = False
            else:
                button_clicked = False
        
        # 顯示轉換結果
        if button_clicked:
            if format_type == 'IEEE':
                converted_text = convert_en_ieee_to_apa(ref)
            elif format_type == 'APA':
                if lang == 'EN':
                    converted_text = convert_en_apa_to_ieee(ref)
                elif lang == 'ZH':
                    fmt = ref.get('format', '')
                    if 'APA' in fmt:
                        converted_text = convert_zh_apa_to_num(ref)
                    elif 'Numbered' in fmt:
                        converted_text = convert_zh_num_to_apa(ref)
            
            st.code(converted_text, language=None)
        
        # 原文
        st.divider()
        st.caption("📍 原始參考文獻文字")
        st.markdown(f"""
            <div style="
                background-color: #f0f2f6;
                border-left: 3px solid #1f77b4;
                padding: 12px 12px 24px 12px;
                border-radius: 4px;
                font-family: monospace;
                font-size: 14px;
                line-height: 1.6;
                white-space: pre-wrap;
                word-wrap: break-word;
                overflow-wrap: break-word;
                margin-bottom: 12px;
            ">
            {ref['original']}
            </div>
            """, unsafe_allow_html=True)

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
        col1, col2, col3 = st.columns([2, 4, 4])
        
        with col1:
            st.markdown(f"""
            <div style="
                background: #FAF0E6;
                border-radius: 30px;
                padding: 15px;
                text-align: center;
                color: #4B2E1E;
                box-shadow: 0 4px 6px rgba(0,0,0,0.3);
                height: 160px;
                display: flex;
                flex-direction: column;
                justify-content: center;
            ">
                <div style="font-size: 25px; opacity: 0.9; margin-bottom: 5px;; font-weight: bold;">內文引用總數</div>
                <div style="font-size: 45px; font-weight: bold;">{len(in_text_citations)}</div>
            </div>
            """, unsafe_allow_html=True)
        
        apa_count = sum(1 for c in in_text_citations if c['format'] == 'APA')
        with col2:
            st.markdown(f"""
            <div style="
                background: rgba(242, 231, 203, 0.8);
                border: 3px solid 	#844200;
                border-radius: 30px;
                padding: 15px;
                text-align: center;
                color: #761A0A;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                height: 160px;
                display: flex;
                flex-direction: column;
                justify-content: center;
            ">
                <div style="font-size: 25px; margin-bottom: 5px;font-weight: bold;">「APA 格式」引用</div>
                <div style="font-size: 45px; font-weight: bold;">{apa_count}</div>
            </div>
            """, unsafe_allow_html=True)
        
        ieee_count = sum(1 for c in in_text_citations if c['format'] == 'IEEE')
        with col3:
            st.markdown(f"""
            <div style="
                background: rgba(242, 231, 203, 0.8);
                border: 3px solid 	#844200;
                border-radius: 30px;
                padding: 15px;
                text-align: center;
                color: #761A0A;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                height: 160px;
                display: flex;
                flex-direction: column;
                justify-content: center;
            ">
                <div style="font-size: 25px; margin-bottom: 5px;font-weight: bold;">「IEEE 格式」引用</div>
                <div style="font-size: 45px; font-weight: bold;">{ieee_count}</div>
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
            st.info("💡 偵測到 IEEE 編號格式")
            #  st.info("💡 偵測到 IEEE 編號格式，啟用**嚴格分割模式**")
            merged_refs = merge_references_ieee_strict(ref_paras)
        else:
            st.info("💡 偵測到 APA 格式")
            # st.info("💡 偵測到一般格式 (APA/中文)，啟用**智慧混合模式**")
            merged_refs = merge_references_unified(ref_paras)
        
        # 解析參考文獻
        parsed_refs = [process_single_reference(r) for r in merged_refs]
        st.session_state.reference_list = parsed_refs
        
        st.info(f"成功解析出 {len(parsed_refs)} 筆參考文獻")
        apa_refs = []
        ieee_refs = []
        for r in parsed_refs:
            if r.get('ref_number'):
                ieee_refs.append(r)   # 有編號 → 一律算 IEEE
            else:
                fmt = str(r.get('format', ''))
                if fmt.startswith('APA'):
                    apa_refs.append(r)
                else:
                    ieee_refs.append(r)

        apa_refs_count = len(apa_refs)
        ieee_refs_count = len(ieee_refs)
        # 統計卡片
        col1, col2, col3 = st.columns([2, 4, 4])
        
        with col1:
            st.markdown(f"""
            <div style="
                background: #FAF0E6;
                border-radius: 30px;
                padding: 15px;
                text-align: center;
                color: #4B2E1E;
                box-shadow: 0 4px 6px rgba(0,0,0,0.3);
                height: 160px;
                display: flex;
                flex-direction: column;
                justify-content: center;
            ">
                <div style="font-size: 25px; opacity: 0.9; margin-bottom: 5px;font-weight: bold;">參考文獻總數</div>
                <div style="font-size: 45px; font-weight: bold;">{len(parsed_refs)}</div>
            </div>
            """, unsafe_allow_html=True)
        
        # apa_refs_count = sum(1 for r in parsed_refs if 'APA' in r.get('format', ''))
        with col2:
            st.markdown(f"""
            <div style="
                background: rgba(242, 231, 203, 0.8);
                border: 3px solid 	#844200;
                border-radius: 30px;
                padding: 15px;
                text-align: center;
                color: #761A0A;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                height: 160px;
                display: flex;
                flex-direction: column;
                justify-content: center;
            ">
                <div style="font-size: 25px; margin-bottom: 5px;font-weight: bold;">「APA」格式</div>
                <div style="font-size: 45px; font-weight: bold;">{apa_refs_count}</div>
            </div>
            """, unsafe_allow_html=True)
        
        # ieee_refs_count = sum(1 for r in parsed_refs if 'IEEE' in r.get('format', ''))
        with col3:
            st.markdown(f"""
            <div style="
                background: rgba(242, 231, 203, 0.8);
                border: 3px solid 	#844200;
                border-radius: 30px;
                padding: 15px;
                text-align: center;
                color: #761A0A;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                height: 160px;
                display: flex;
                flex-direction: column;
                justify-content: center;
            ">
                <div style="font-size: 25px; margin-bottom: 5px;font-weight: bold;">「IEEE」格式</div>
                <div style="font-size: 45px; font-weight: bold;">{ieee_refs_count}</div>
            </div>
            """, unsafe_allow_html=True)
        
        # with col4:
        #     st.markdown(f"""
        #     <div style="
        #         background: linear-gradient(135deg, #ff7675 0%, #ff9a3d 100%);
        #         border-radius: 12px;
        #         padding: 20px;
        #         text-align: center;
        #         color: white;
        #         box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        #     ">
        #         <div style="font-size: 18px; opacity: 0.9; margin-bottom: 6px;">其他/混合</div>
        #         <div style="font-size: 28px; font-weight: bold;">0</div>
        #     </div>
        #     """, unsafe_allow_html=True)
        
        # with col5:
        #     st.markdown(f"""
        #     <div style="
        #         background: linear-gradient(135deg, #95de64 0%, #b3e5fc 100%);
        #         border-radius: 12px;
        #         padding: 20px;
        #         text-align: center;
        #         color: #333;
        #         box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        #     ">
        #         <div style="font-size: 18px; opacity: 0.9; margin-bottom: 6px;">未知格式</div>
        #         <div style="font-size: 28px; font-weight: bold;">0</div>
        #     </div>
        #     """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # IEEE 參考文獻展示
        st.markdown("### 📖 IEEE 格式參考文獻")
        ieee_list = ieee_refs
        if ieee_list:
            for i, ref in enumerate(ieee_list, 1):
                display_reference_with_details(ref, i, format_type='IEEE')
        else:
            st.info("無 IEEE 格式參考文獻")

        st.markdown("---")

        # APA 參考文獻展示
        st.markdown("### 📚 APA 與其他格式參考文獻")
        apa_list =  apa_refs
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
            st.session_state.comparison_done = True
            
            st.success("✅ 比對完成！")


# ==================== 顯示比對結果 ====================

if st.session_state.get('comparison_done', False):
    st.subheader("📊 比對結果報告")
    
    missing_count = len(st.session_state.get('missing_refs', []))
    unused_count = len(st.session_state.get('unused_refs', []))

    tab1, tab2 = st.tabs([
        f"❌ 遺漏的參考文獻 ({missing_count})", 
        f"⚠️ 未使用的參考文獻 ({unused_count})"
    ])
    
    with tab1:
        st.caption("💡 說明：這些引用出現在內文中，但在參考文獻列表裡找不到對應項目。")

        missing_refs = st.session_state.get('missing_refs', [])
        
        if not missing_refs:
            st.success("太棒了！所有內文引用都在參考文獻列表中找到了。")
        else:
            for i, item in enumerate(missing_refs, 1):
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
        
        unused_refs = st.session_state.get('unused_refs', [])
        
        if not unused_refs:
            st.success("太棒了！所有參考文獻都在內文中被有效引用。")
        else:
            for i, item in enumerate(unused_refs, 1):
                st.warning(f"{i}. **{item['original']}**", icon="🗑️")
                
    st.markdown("---")
    st.subheader("📥 匯出比對結果")

    missing_refs = st.session_state.get('missing_refs', [])
    unused_refs = st.session_state.get('unused_refs', [])  

    # 先準備好所有資料
    # ---- 準備 JSON 資料 ----
    export_obj = {
        "missing_references": missing_refs,
        "unused_references": unused_refs,
    }
    json_bytes = json.dumps(export_obj, ensure_ascii=False, indent=2).encode("utf-8")

    # ---- 準備 CSV 資料 ----
    def to_df(items, kind):
        if not items:
            return pd.DataFrame(columns=["type", "original", "format", "ref_number", "author", "year"])
        rows = []
        for x in items:
            rows.append({
                "type": kind,                       # missing / unused
                "original": x.get("original", ""),
                "format": x.get("format", ""),
                "ref_number": x.get("ref_number", ""),
                "author": x.get("author", ""),
                "year": x.get("year", ""),
            })
        return pd.DataFrame(rows)

    df_missing = to_df(missing_refs, "missing")
    df_unused = to_df(unused_refs, "unused")
    df_export = pd.concat([df_missing, df_unused], ignore_index=True)
    csv_bytes = df_export.to_csv(index=False).encode("utf-8")

    # ---- 顯示下載按鈕 ----
    col_json, col_csv = st.columns(2)

    with col_json:
        st.download_button(
            label="⬇️ 下載 JSON(遺漏 / 未使用文獻)",
            data=json_bytes,
            file_name=f"citation_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True,
            key="download_json_button"
        )

    with col_csv:
        st.download_button(
            label="⬇️ 下載 CSV(遺漏 / 未使用文獻)",
            data=csv_bytes,
            file_name=f"citation_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True,
            key="download_csv_button"
        )

# ==================== 查看暫存資料 ====================

if st.session_state.in_text_citations or st.session_state.reference_list:
    with st.expander("🔍 查看完整暫存資料（JSON 格式）"):
        st.json({
            "in_text_citations": st.session_state.in_text_citations,
            "reference_list": st.session_state.reference_list,
            "verified_references": st.session_state.verified_references
        })