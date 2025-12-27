import streamlit as st
import json
import pandas as pd
from datetime import datetime
from checker import check_references

def display_comparison_button():
    """顯示比對按鈕並執行比對"""
    st.header("🚀 交叉比對分析")
    st.info("👆 請確認上方解析結果無誤後，點擊下方按鈕開始檢查。")
    
    if st.button("開始交叉比對", type="primary", use_container_width=True):
        if not st.session_state.in_text_citations or not st.session_state.reference_list:
            st.error("❌ 資料不足，無法比對。請確認是否已成功解析內文引用與參考文獻。")
        else:
            with st.spinner("正在進行雙向交叉比對..."):
                missing, unused, year_errors = check_references(
                    st.session_state.in_text_citations,
                    st.session_state.reference_list
                )
                
                st.session_state.missing_refs = missing
                st.session_state.unused_refs = unused
                st.session_state.year_error_refs = year_errors
                st.session_state.comparison_done = True
                
                st.success("✅ 比對完成！")

def display_missing_tab():
    """顯示遺漏的參考文獻 Tab"""
    st.caption("💡 說明：這些引用出現在內文中，但在參考文獻列表裡找不到對應項目。")
    
    missing_refs = st.session_state.get('missing_refs', [])
    
    if not missing_refs:
        st.success("✅ 太棒了！所有內文引用都在參考文獻列表中找到了。")
    else:
        for i, item in enumerate(missing_refs, 1):
            st.error(f"{i}. **{item['original']}** (格式: {item['format']})", icon="🚨")

def display_unused_tab():
    """顯示未使用的參考文獻 Tab"""
    st.caption("💡 說明：這些文獻列在參考文獻列表中，但在內文中從未被引用過。")
    
    unused_refs = st.session_state.get('unused_refs', [])
    pure_unused = [item for item in unused_refs if not item.get('year_mismatch')]
    
    if not pure_unused:
        st.success("✅ 太棒了！所有參考文獻都在內文中被有效引用。")
    else:
        for i, item in enumerate(pure_unused, 1):
            st.warning(f"{i}. **{item.get('original', '未知文獻')[:150]}...**")

def display_year_error_tab():
    """顯示疑似年份錯誤 Tab"""
    st.caption("💡 說明：這些文獻的作者匹配，但年份不一致。")
    
    year_error_refs = st.session_state.get('year_error_refs', [])
    
    if not year_error_refs:
        st.success("✅ 沒有發現年份錯誤。")
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
                st.error(f"**{i}. {item.get('original', '未知文獻')[:100]}...**")
                
                with st.expander("⚠️ 疑似年份引用錯誤", expanded=False):
                    for mismatch in item.get('year_mismatch', []):
                        st.write(f"文中引用的是 {mismatch['citation']}")

def display_export_section():
    """顯示匯出功能區"""
    st.subheader("📥 匯出比對結果")
    
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
        if not items:
            return pd.DataFrame(columns=["type", "original", "format", "ref_number", "author", "year", "error_detail"])
        rows = []
        for x in items:
            error_detail = ""
            if 'year_mismatch' in x and x['year_mismatch']:
                mismatch_info = []
                for m in x['year_mismatch']:
                    mismatch_info.append(f"內文:{m['cited_year']}→正確:{m['correct_year']}")
                error_detail = "; ".join(mismatch_info)
            
            rows.append({
                "type": kind,
                "original": x.get("original", ""),
                "format": x.get("format", ""),
                "ref_number": x.get("ref_number", ""),
                "author": x.get("author", ""),
                "year": x.get("year", ""),
                "error_detail": error_detail
            })
        return pd.DataFrame(rows)
    
    df_missing = to_df(missing_refs, "missing")
    df_unused = to_df(unused_refs, "unused")
    df_year_error = to_df(year_error_refs, "year_error")
    df_export = pd.concat([df_missing, df_unused, df_year_error], ignore_index=True)
    csv_bytes = df_export.to_csv(index=False).encode("utf-8")
    
    # 下載按鈕
    col_json, col_csv = st.columns(2)
    
    with col_json:
        st.download_button(
            label="⬇️ 下載 JSON(遺漏 / 未使用 / 年份錯誤)",
            data=json_bytes,
            file_name=f"citation_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True,
            key="download_json_button"
        )
    
    with col_csv:
        st.download_button(
            label="⬇️ 下載 CSV(遺漏 / 未使用 / 年份錯誤)",
            data=csv_bytes,
            file_name=f"citation_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True,
            key="download_csv_button"
        )

def display_comparison_results():
    """顯示完整的比對結果（含三個 Tabs 和匯出）"""
    st.subheader("📊 比對結果報告")
    
    missing_count = len(st.session_state.get('missing_refs', []))
    unused_refs_all = st.session_state.get('unused_refs', [])
    pure_unused_count = len([r for r in unused_refs_all if not r.get('year_mismatch')])
    year_error_count = len(st.session_state.get('year_error_refs', []))
    
    tab1, tab2, tab3 = st.tabs([
        f"❌ 遺漏的參考文獻 ({missing_count})",
        f"⚠️ 未使用的參考文獻 ({pure_unused_count})",
        f"📅 疑似年份錯誤 ({year_error_count})"
    ])
    
    with tab1:
        display_missing_tab()
    
    with tab2:
        display_unused_tab()
    
    with tab3:
        display_year_error_tab()
    
    st.markdown("---")
    
    display_export_section()