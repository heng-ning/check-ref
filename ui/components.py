import streamlit as st
import re
# 引用解析相關
from parsers.ieee.ieee_converter import convert_en_ieee_to_apa
from parsers.apa.apa_converter import (
    format_pages_display,
    convert_en_apa_to_ieee,
    convert_zh_apa_to_num,
    convert_zh_num_to_apa
)
# 引用翻譯
from utils.i18n import get_text


def display_reference_with_details(ref, index, format_type='IEEE'):
    """ 統一顯示參考文獻的詳細資訊 """
    title_text = ref.get('title', get_text("no_title"))
    ref_num = ref.get('ref_number', str(index))
    
    # 根據來源類型決定圖示
    lang = ref.get('lang', 'EN')
    
    with st.expander(f"[{ref_num}] {title_text}", expanded=False):
        # 作者
        authors_data = ref.get('authors')
        if authors_data:
            st.markdown(f"**{get_text('authors')}**")
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
            st.markdown(f"**{get_text('title')}**")
            st.markdown(f"　└─ {ref['title']}")
        
        # 書名（若為書籍章節）
        if ref.get('book_title'):
            st.markdown(f"**{get_text('book_title')}**")
            st.markdown(f"　└─ {ref['book_title']}")

        # 論文集名稱（若為會議論文）
        if ref.get('proceedings_title'):
            st.markdown(f"**{get_text('proceedings')}**")
            st.markdown(f"　└─ In {ref['proceedings_title']}")
        
        # 編輯
        if ref.get('editors'):
            st.markdown(f"**{get_text('editors')}**")
            st.markdown(f"　└─ {ref['editors']}")
        
        # 來源（會議、期刊、出版社）
        if format_type == 'IEEE':
            source_show = (ref.get('conference_name') or 
                        ref.get('journal_name') or 
                        ref.get('source'))
        else:  # APA
            source_show = (ref.get('source') or 
                        ref.get('publisher'))

        if source_show:
            if ref.get('conference_name'):
                label = get_text("conf_name")
            elif ref.get('journal_name'):
                label = get_text("journal_name")
            elif ref.get('source'):
                label = get_text("journal_name") if format_type == 'IEEE' else get_text("journal_name")
            elif ref.get('publisher'):
                label = get_text("publisher")
            else:
                label = get_text("source")
            st.markdown(f"**📖 {label}**")
            st.markdown(f"　└─ {source_show}")
        
        # 卷期
        if ref.get('volume') or ref.get('issue'):
            volume_val = ref.get('volume')
            issue_val = ref.get('issue')
            
            if volume_val and issue_val:
                issue_str = str(issue_val)
                is_numeric_issue = bool(
                    issue_str.isdigit() or 
                    re.match(r'^\d+[\-–—]\d+$', issue_str) or 
                    re.match(r'^\d+,\s*\d+$', issue_str)
                )
                
                if is_numeric_issue:
                    vi_display = f"Vol. {volume_val}, No. {issue_str}"
                else:
                    vi_display = f"Vol. {volume_val}({issue_str})"
            elif volume_val:
                vi_display = f"Vol. {volume_val}"
            elif issue_val:
                vi_display = f"No. {issue_val}"
            else:
                vi_display = None
            
            if vi_display:
                st.markdown(f"**{get_text('volume')}**")
                st.markdown(f"　└─ {vi_display}")
        
        # 版次
        if ref.get('edition'):
            st.markdown(f"**{get_text('edition')}**")
            st.markdown(f"　└─ {ref['edition']}")

        # 頁碼/文章編號
        if ref.get('article_number'):
            st.markdown(f"**{get_text('article_num')}**")
            st.markdown(f"　└─ {ref['article_number']}")
        
        if ref.get('pages'):
            formatted_pages = format_pages_display(ref['pages'])
            st.markdown(f"**{get_text('pages')}**")
            st.markdown(f"　└─ {formatted_pages}")
        
        # 年份與月份
        if ref.get('year'):
            date_str = ref['year']
            if ref.get('month'):
                date_str = f"{ref['month']} {date_str}"
            st.markdown(f"**{get_text('date')}**")
            st.markdown(f"　└─ {date_str}")
        
        # 文件類型
        if ref.get('document_type'):
            st.markdown(f"**{get_text('doc_type')}**")
            st.markdown(f"　└─ {ref['document_type']}")
        
        # 電子資源
        if ref.get('doi'):
            st.markdown(f"**{get_text('doi')}**")
            st.markdown(f"　└─ [{ref['doi']}](https://doi.org/{ref['doi']})")
        
        if ref.get('url'):
            st.markdown(f"**{get_text('url')}**")
            st.markdown(f"　└─ [{ref['url']}]({ref['url']})")

        col_title, col_button = st.columns([3, 1])
        with col_title:
            st.markdown(get_text("convert_fmt"))
    
        with col_button:
            # 根據格式顯示不同的轉換按鈕
            if format_type == 'IEEE':
                button_clicked = st.button(get_text("to_apa"), key=f"ref_to_apa_{index}", use_container_width=True)
            elif format_type == 'APA':
                if lang == 'EN':
                    button_clicked = st.button(get_text("to_ieee"), key=f"ref_to_ieee_{index}", use_container_width=True)
                elif lang == 'ZH':
                    fmt = ref.get('format', '')
                    if 'APA' in fmt:
                        button_clicked = st.button(get_text("to_num"), key=f"ref_to_num_{index}", use_container_width=True)
                    elif 'Numbered' in fmt:
                        button_clicked = st.button(get_text("to_apa"), key=f"ref_to_apa_{index}", use_container_width=True)
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
        st.caption(get_text("orig_text"))
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

# render_stat_card 保持不變，或也加上多語言參數

def render_citation_list(citations):
    """
    渲染內文引用列表
    """
    if not citations:
        st.info(get_text("no_in_text_citation"))
        return
    
    with st.expander(get_text("in_text_citation_list")):
        for i, cite in enumerate(citations, 1):
            if cite['format'] == 'APA':
                co_author_text = f" & {cite['co_author']}" if cite['co_author'] else ""
                st.markdown(
                    f"{i}. `{cite['original']}` — "
                    f"**[{cite['format']}]** "
                    f"{get_text('author_label')}：**{cite['author']}{co_author_text}** | "
                    f"{get_text('year_label')}：**{cite['year']}** | "
                    f"{get_text('type_label')}：{cite['type']}"
                )
            else:
                ref_display = cite.get('ref_number', '?')
                if cite.get('all_numbers') and len(cite['all_numbers']) > 1:
                    all_nums_str = ", ".join(cite['all_numbers'])
                    ref_display = f"{all_nums_str}"
                
                st.markdown(
                    f"{i}. `{cite['original']}` — "
                    f"**[{cite['format']}]** "
                    f"{get_text('ref_num')}：**{ref_display}**"
                )
