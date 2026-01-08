import streamlit as st
import re
from parsers.ieee.ieee_converter import convert_en_ieee_to_apa
from parsers.apa.apa_converter import (
    format_pages_display,
    convert_en_apa_to_ieee,
    convert_zh_apa_to_num,
    convert_zh_num_to_apa
)

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

        # 論文集名稱（若為會議論文）
        if ref.get('proceedings_title'):
            st.markdown(f"**📄 論文集名稱**")
            st.markdown(f"　└─ In {ref['proceedings_title']}")
        
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
        
        if ref.get('pages'):
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

def render_stat_card(title, value, color_scheme="primary"):
    """
    渲染統計卡片
    
    Args:
        title: 卡片標題
        value: 顯示的數值
        color_scheme: 配色方案 ("primary", "secondary", "accent")
    """
    # 預設值初始化
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
    else:  # accent or other
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

def render_citation_list(citations):
    """
    渲染內文引用列表
    
    Args:
        citations: 引用列表
    """
    if not citations:
        st.info("未找到任何內文引用")
        return
    
    with st.expander("📋 查看所有內文引用"):
        for i, cite in enumerate(citations, 1):
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
                ref_display = cite.get('ref_number', '?')
                
                # 如果有 all_numbers 且數量大於 1，顯示完整列表
                if cite.get('all_numbers') and len(cite['all_numbers']) > 1:
                    # 將列表轉為字串，如 "6, 7, 8"
                    all_nums_str = ", ".join(cite['all_numbers'])
                    ref_display = f"{all_nums_str}"
                
                st.markdown(
                    f"{i}. `{cite['original']}` — "
                    f"**[{cite['format']}]** "
                    f"參考編號：**{ref_display}**"
                )