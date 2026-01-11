import streamlit as st
import json
import csv
import pandas as pd
from datetime import datetime
from checker import check_references
from utils.i18n import get_text # 假設您有匯入翻譯

def run_comparison():
    """執行交叉比對並更新 session_state"""
    if not st.session_state.in_text_citations or not st.session_state.reference_list:
        return False
        
    missing, unused, year_errors = check_references(
        st.session_state.in_text_citations,
        st.session_state.reference_list
    )
    
    st.session_state.missing_refs = missing
    st.session_state.unused_refs = unused
    st.session_state.year_error_refs = year_errors
    st.session_state.comparison_done = True
    return True

# def display_comparison_button():
#     """顯示比對按鈕（手動觸發用）"""
#     st.header(get_text("comparison_title"))
    
#     if st.button(get_text("manual_recompare"), type="secondary", use_container_width=True):
#         if not run_comparison():
#              st.error(get_text("compare_fail_msg"))
#         else:
#              st.success(get_text("compare_success"))


def display_missing_tab():
    """顯示遺漏的參考文獻 Tab"""
    st.caption(get_text("missing_desc"))
    
    missing_refs = st.session_state.get('missing_refs', [])
    
    if not missing_refs:
        st.success(get_text("missing_success"))
    else:
        for i, item in enumerate(missing_refs, 1):
            st.error(f"{i}. **{item['original']}** ({get_text('fmt_label')}: {item['format']})", icon="🚨")


def display_unused_tab():
    """顯示未使用的參考文獻 Tab"""
    st.caption(get_text("unused_desc"))
    
    unused_refs = st.session_state.get('unused_refs', [])
    pure_unused = [item for item in unused_refs if not item.get('year_mismatch')]
    
    if not pure_unused:
        st.success(get_text("unused_success"))
    else:
        for i, item in enumerate(pure_unused, 1):
            st.warning(f"{i}. **{item.get('original', get_text('unknown_ref'))[:150]}...**")


def display_year_error_tab():
    """顯示疑似年份錯誤 Tab"""
    st.caption(get_text("year_error_desc"))
    
    year_error_refs = st.session_state.get('year_error_refs', [])
    
    if not year_error_refs:
        st.success(get_text("year_error_success"))
    else:
        # 去重
        seen_originals = set()
        unique_refs = []
        for item in year_error_refs:
            original = item.get('original', '')
            if original not in seen_originals:
                seen_originals.add(original)
                unique_refs.append(item)
        
        for i, item in enumerate(unique_refs, 1):
            with st.container():
                st.error(f"**{i}. {item.get('original', get_text('unknown_ref'))[:100]}...**")
                
                with st.expander(get_text("year_error_expander"), expanded=False):
                    for mismatch in item.get('year_mismatch', []):
                        st.write(f"{get_text('citation_in_text')} {mismatch['citation']}")


def display_export_section():
    """顯示匯出功能區"""
    st.subheader(get_text("export_title"))
    
    missing_refs = st.session_state.get('missing_refs', [])
    unused_refs = st.session_state.get('unused_refs', [])
    year_error_refs = st.session_state.get('year_error_refs', [])
    
    # 準備 JSON
    export_obj = {
        "missing_references": missing_refs,
        "unused_references": unused_refs,
        "year_error_references": year_error_refs
    }
    json_bytes = json.dumps(export_obj, ensure_ascii=False, indent=2).encode("utf-8")
    
    # 準備 CSV
    def to_df(items, kind):
        # 定義 CSV 欄位名稱 (如果要支援多語言匯出，這裡也要用 get_text)
        # 但通常 CSV 欄位名稱保持英文比較好處理，這裡示範用多語言表頭
        columns = [
            get_text("csv_header_type"), 
            get_text("csv_header_original"), 
            get_text("csv_header_format"), 
            get_text("csv_header_ref_num"), 
            get_text("csv_header_author"), 
            get_text("csv_header_year"), 
            get_text("csv_header_detail")
        ]
        
        if not items:
            return pd.DataFrame(columns=columns)
            
        rows = []
        for x in items:
            error_detail = ""
            if 'year_mismatch' in x and x['year_mismatch']:
                mismatch_info = []
                for m in x['year_mismatch']:
                    # 使用格式化字串
                    detail_str = get_text("err_detail_format", cited=m['cited_year'], correct=m['correct_year'])
                    mismatch_info.append(detail_str)
                error_detail = "; ".join(mismatch_info)
            
            rows.append({
                columns[0]: kind,
                columns[1]: x.get("original", ""),
                columns[2]: x.get("format", ""),
                columns[3]: x.get("ref_number", ""),
                columns[4]: x.get("author", ""),
                columns[5]: x.get("year", ""),
                columns[6]: error_detail
            })
        return pd.DataFrame(rows)
    
    df_missing = to_df(missing_refs, "missing")
    df_unused = to_df(unused_refs, "unused")
    df_year_error = to_df(year_error_refs, "year_error")
    df_export = pd.concat([df_missing, df_unused, df_year_error], ignore_index=True)
    
    # 使用 utf-8-sig + quoting=QUOTE_ALL 解決 Excel 亂碼與欄位錯位
    csv_bytes = df_export.to_csv(index=False, quoting=csv.QUOTE_ALL).encode("utf-8-sig")
    
    # 下載按鈕
    col_json, col_csv = st.columns(2)
    
    with col_json:
        st.download_button(
            label=get_text("download_json"),
            data=json_bytes,
            file_name=f"citation_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True,
            key="download_json_button"
        )
    
    with col_csv:
        st.download_button(
            label=get_text("download_csv"),
            data=csv_bytes,
            file_name=f"citation_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True,
            key="download_csv_button"
        )


def display_comparison_results():
    """顯示完整的比對結果（含三個 Tabs 和匯出）"""
    st.subheader(get_text("report_title"))
    
    missing_count = len(st.session_state.get('missing_refs', []))
    unused_refs_all = st.session_state.get('unused_refs', [])
    pure_unused_count = len([r for r in unused_refs_all if not r.get('year_mismatch')])
    year_error_count = len(st.session_state.get('year_error_refs', []))
    
    tab1, tab2, tab3 = st.tabs([
        get_text("tab_missing", count=missing_count),
        get_text("tab_unused", count=pure_unused_count),
        get_text("tab_year_error", count=year_error_count)
    ])
    
    with tab1:
        display_missing_tab()
    
    with tab2:
        display_unused_tab()
    
    with tab3:
        display_year_error_tab()
    
    st.markdown("---")
    
    display_export_section()