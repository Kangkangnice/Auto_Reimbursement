import streamlit as st
import os
import sys
import pandas as pd

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SRC_DIR)
sys.path.insert(0, SRC_DIR)

import database as db
import utils

st.set_page_config(
    page_title="数据预览 - 报销管理系统",
    page_icon="📝",
    layout="wide"
)

st.markdown("# 📝 数据预览")
st.markdown("---")

month_folders = db.get_month_folders()

if not month_folders:
    st.warning("暂无数据，请先在 **📊 数据导入** 页面上传文件")
    st.stop()

col_select, col_info = st.columns([1, 2])

with col_select:
    selected_month = st.selectbox(
        "选择月份",
        options=month_folders,
        index=0
    )

with col_info:
    checkin_records = db.get_checkin_records(selected_month)
    invoice_records = db.get_invoice_records(selected_month)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("打卡记录", f"{len(checkin_records)} 条")
    with col2:
        st.metric("发票记录", f"{len(invoice_records)} 条")
    with col3:
        total_amount = sum(r['amount'] for r in invoice_records)
        st.metric("发票总金额", f"¥{total_amount:.2f}")

st.markdown("---")

tab1, tab2, tab3 = st.tabs(["📋 打卡记录", "🧾 发票记录", "✅ 报销资格检查"])

with tab1:
    st.markdown("### 打卡记录列表")
    
    if checkin_records:
        df_checkin = pd.DataFrame(checkin_records)
        df_checkin['date'] = pd.to_datetime(df_checkin['date'])
        df_checkin = df_checkin.sort_values('date')
        df_checkin['weekday'] = df_checkin['date'].apply(lambda x: utils.get_weekday_name(x.strftime('%Y-%m-%d')))
        df_checkin['date_str'] = df_checkin['date'].dt.strftime('%Y-%m-%d')
        
        df_display = df_checkin[['date_str', 'weekday', 'work_hours', 'source_file']].copy()
        df_display.columns = ['日期', '星期', '工作时长', '来源文件']
        
        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "工作时长": st.column_config.NumberColumn("工作时长", format="%.1f 小时"),
            }
        )
        
        st.markdown("#### 编辑打卡记录")
        
        col_edit1, col_edit2 = st.columns([1, 1])
        
        with col_edit1:
            edit_id = st.selectbox(
                "选择要编辑的记录",
                options=df_checkin['id'].tolist(),
                format_func=lambda x: df_checkin[df_checkin['id']==x]['date_str'].values[0] + f" ({df_checkin[df_checkin['id']==x]['work_hours'].values[0]}小时)",
                key='edit_checkin_select'
            )
        
        with col_edit2:
            if edit_id:
                current_hours = df_checkin[df_checkin['id']==edit_id]['work_hours'].values[0]
                new_hours = st.number_input("工作时长", min_value=0.0, max_value=24.0, value=float(current_hours), step=0.5, key='edit_checkin_hours')
                
                if st.button("保存修改", key='save_checkin_btn'):
                    db.update_checkin_record(edit_id, new_hours)
                    st.success("修改成功！")
                    st.rerun()
        
        st.markdown("#### 删除打卡记录")
        
        delete_id = st.selectbox(
            "选择要删除的记录",
            options=df_checkin['id'].tolist(),
            format_func=lambda x: df_checkin[df_checkin['id']==x]['date_str'].values[0] + f" ({df_checkin[df_checkin['id']==x]['work_hours'].values[0]}小时)",
            key='delete_checkin_select'
        )
        
        if st.button("删除记录", type="secondary", key='delete_checkin_btn'):
            db.delete_checkin_record(delete_id)
            st.success("删除成功！")
            st.rerun()
            
    else:
        st.info("该月份暂无打卡记录")

with tab2:
    st.markdown("### 发票记录列表")
    
    if invoice_records:
        df_invoice = pd.DataFrame(invoice_records)
        df_invoice['date'] = pd.to_datetime(df_invoice['date'])
        df_invoice = df_invoice.sort_values('date')
        df_invoice['date_str'] = df_invoice['date'].dt.strftime('%Y-%m-%d')
        
        df_display = df_invoice[['date_str', 'amount', 'company', 'start_location', 'end_location', 'source_file', 'invoice_file']].copy()
        df_display.columns = ['日期', '金额', '服务商', '起点', '终点', '行程单', '发票单']
        
        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "金额": st.column_config.NumberColumn("金额", format="¥%.2f"),
            }
        )
        
        st.markdown("#### 编辑发票记录")
        
        col_edit1, col_edit2 = st.columns([1, 1])
        
        with col_edit1:
            edit_invoice_id = st.selectbox(
                "选择要编辑的记录",
                options=df_invoice['id'].tolist(),
                format_func=lambda x: df_invoice[df_invoice['id']==x]['date_str'].values[0] + f" (¥{df_invoice[df_invoice['id']==x]['amount'].values[0]:.2f})",
                key='edit_invoice_select'
            )
        
        with col_edit2:
            if edit_invoice_id:
                current_record = df_invoice[df_invoice['id']==edit_invoice_id].iloc[0]
                
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    new_amount = st.number_input("金额", min_value=0.0, value=float(current_record['amount']), step=0.01, key='edit_invoice_amount')
                    new_start = st.text_input("起点", value=current_record['start_location'], key='edit_invoice_start')
                with col_f2:
                    new_end = st.text_input("终点", value=current_record['end_location'], key='edit_invoice_end')
                    new_company = st.text_input("服务商", value=current_record['company'], key='edit_invoice_company')
                
                if st.button("保存修改", key='save_invoice_btn'):
                    db.update_invoice_record(
                        edit_invoice_id,
                        amount=new_amount,
                        start_location=new_start,
                        end_location=new_end,
                        company=new_company
                    )
                    st.success("修改成功！")
                    st.rerun()
        
        st.markdown("#### 删除发票记录")
        
        delete_invoice_id = st.selectbox(
            "选择要删除的记录",
            options=df_invoice['id'].tolist(),
            format_func=lambda x: df_invoice[df_invoice['id']==x]['date_str'].values[0] + f" (¥{df_invoice[df_invoice['id']==x]['amount'].values[0]:.2f})",
            key='delete_invoice_select'
        )
        
        if st.button("删除记录", type="secondary", key='delete_invoice_btn'):
            db.delete_invoice_record(delete_invoice_id)
            st.success("删除成功！")
            st.rerun()
            
    else:
        st.info("该月份暂无发票记录")

with tab3:
    st.markdown("### 报销资格检查")
    
    if checkin_records:
        config = db.get_config('reimburse_rules') or {
            'night_meal': {
                'dinner_threshold': 9.5,
                'dinner_amount': 18,
                'night_threshold': 12,
                'night_amount': 20
            },
            'taxi': {
                'threshold': 11.0
            }
        }
        
        dinner_threshold = config['night_meal']['dinner_threshold']
        night_threshold = config['night_meal']['night_threshold']
        taxi_threshold = config['taxi']['threshold']
        
        st.markdown(f"""
        **当前报销规则：**
        - 晚餐报销：工作时长 ≥ {dinner_threshold} 小时，金额 ¥18
        - 夜宵报销：工作时长 ≥ {night_threshold} 小时，金额 ¥20
        - 打车报销：工作时长 > {taxi_threshold} 小时
        """)
        
        st.markdown("---")
        
        check_results = []
        
        for record in checkin_records:
            work_hours = record['work_hours']
            date_str = record['date'] if isinstance(record['date'], str) else record['date'].strftime('%Y-%m-%d')
            
            dinner_eligible, dinner_amount, dinner_reason = utils.check_reimburse_eligibility(work_hours, 'dinner')
            night_eligible, night_amount, night_reason = utils.check_reimburse_eligibility(work_hours, 'night')
            taxi_eligible, _, taxi_reason = utils.check_reimburse_eligibility(work_hours, 'taxi')
            
            check_results.append({
                '日期': date_str,
                '工作时长': f"{work_hours:.1f}h",
                '晚餐报销': '✅' if dinner_eligible else '❌',
                '夜宵报销': '✅' if night_eligible else '❌',
                '打车报销': '✅' if taxi_eligible else '❌',
                '备注': dinner_reason if dinner_eligible else taxi_reason
            })
        
        df_results = pd.DataFrame(check_results)
        st.dataframe(df_results, use_container_width=True, hide_index=True)
        
        eligible_dinner = sum(1 for r in check_results if r['晚餐报销'] == '✅')
        eligible_night = sum(1 for r in check_results if r['夜宵报销'] == '✅')
        eligible_taxi = sum(1 for r in check_results if r['打车报销'] == '✅')
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("符合晚餐报销", f"{eligible_dinner} 天", f"¥{eligible_dinner * 18}")
        with col2:
            st.metric("符合夜宵报销", f"{eligible_night} 天", f"¥{eligible_night * 20}")
        with col3:
            st.metric("符合打车报销", f"{eligible_taxi} 天")
            
    else:
        st.info("该月份暂无打卡记录，无法检查报销资格")

st.markdown("---")

st.markdown("### 📊 数据统计")

if checkin_records or invoice_records:
    col_stat1, col_stat2 = st.columns(2)
    
    with col_stat1:
        if checkin_records:
            st.markdown("#### 工作时长分布")
            df_hours = pd.DataFrame(checkin_records)
            df_hours['work_hours'] = pd.to_numeric(df_hours['work_hours'])
            
            avg_hours = df_hours['work_hours'].mean()
            max_hours = df_hours['work_hours'].max()
            min_hours = df_hours['work_hours'].min()
            
            st.write(f"- 平均工作时长: **{avg_hours:.1f}** 小时")
            st.write(f"- 最长工作时长: **{max_hours:.1f}** 小时")
            st.write(f"- 最短工作时长: **{min_hours:.1f}** 小时")
    
    with col_stat2:
        if invoice_records:
            st.markdown("#### 发票金额分布")
            df_amount = pd.DataFrame(invoice_records)
            df_amount['amount'] = pd.to_numeric(df_amount['amount'])
            
            avg_amount = df_amount['amount'].mean()
            max_amount = df_amount['amount'].max()
            min_amount = df_amount['amount'].min()
            
            st.write(f"- 平均发票金额: **¥{avg_amount:.2f}**")
            st.write(f"- 最高发票金额: **¥{max_amount:.2f}**")
            st.write(f"- 最低发票金额: **¥{min_amount:.2f}**")
