import streamlit as st
import os
import sys
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SRC_DIR)
sys.path.insert(0, SRC_DIR)

import database as db

st.set_page_config(
    page_title="统计分析 - 报销管理系统",
    page_icon="📈",
    layout="wide"
)

st.markdown("# 📈 统计分析")
st.markdown("---")

stats = db.get_statistics()

if stats['total_checkin_records'] == 0 and stats['total_invoice_records'] == 0:
    st.warning("暂无数据，请先在 **📊 数据导入** 页面上传文件")
    st.stop()

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("打卡记录总数", f"{stats['total_checkin_records']} 条")

with col2:
    st.metric("发票记录总数", f"{stats['total_invoice_records']} 条")

with col3:
    st.metric("发票总金额", f"¥{stats['total_invoice_amount']:.2f}")

with col4:
    st.metric("导出次数", f"{stats['total_exports']} 次")

st.markdown("---")

tab1, tab2, tab3 = st.tabs(["📊 月度统计", "🧾 发票分析", "📋 历史记录"])

with tab1:
    st.markdown("### 月度报销统计")
    
    month_folders = db.get_month_folders()
    
    if month_folders:
        monthly_data = []
        
        for month in month_folders:
            checkin_records = db.get_checkin_records(month)
            invoice_records = db.get_invoice_records(month)
            reimburse_records = db.get_reimburse_records(month)
            
            config = db.get_config('reimburse_rules') or {
                'night_meal': {
                    'dinner_threshold': 9.5,
                    'dinner_amount': 18,
                    'night_threshold': 12,
                    'night_amount': 20
                }
            }
            
            dinner_count = sum(1 for r in checkin_records if r['work_hours'] >= config['night_meal']['dinner_threshold'])
            night_count = sum(1 for r in checkin_records if r['work_hours'] >= config['night_meal']['night_threshold'])
            
            dinner_amount = dinner_count * config['night_meal']['dinner_amount']
            night_amount = night_count * config['night_meal']['night_amount']
            taxi_amount = sum(r['amount'] for r in invoice_records)
            
            monthly_data.append({
                '月份': month,
                '打卡天数': len(checkin_records),
                '晚餐报销天数': dinner_count,
                '夜宵报销天数': night_count,
                '晚餐金额': dinner_amount,
                '夜宵金额': night_amount,
                '打车金额': taxi_amount,
                '总金额': dinner_amount + night_amount + taxi_amount
            })
        
        df_monthly = pd.DataFrame(monthly_data)
        
        st.dataframe(
            df_monthly,
            use_container_width=True,
            hide_index=True,
            column_config={
                "晚餐金额": st.column_config.NumberColumn("晚餐金额", format="¥%.0f"),
                "夜宵金额": st.column_config.NumberColumn("夜宵金额", format="¥%.0f"),
                "打车金额": st.column_config.NumberColumn("打车金额", format="¥%.2f"),
                "总金额": st.column_config.NumberColumn("总金额", format="¥%.2f"),
            }
        )
        
        st.markdown("---")
        
        st.markdown("### 月度报销金额趋势")
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            name='晚餐',
            x=df_monthly['月份'],
            y=df_monthly['晚餐金额'],
            marker_color='#1f77b4'
        ))
        
        fig.add_trace(go.Bar(
            name='夜宵',
            x=df_monthly['月份'],
            y=df_monthly['夜宵金额'],
            marker_color='#ff7f0e'
        ))
        
        fig.add_trace(go.Bar(
            name='打车',
            x=df_monthly['月份'],
            y=df_monthly['打车金额'],
            marker_color='#2ca02c'
        ))
        
        fig.update_layout(
            barmode='stack',
            xaxis_title='月份',
            yaxis_title='金额（元）',
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
    else:
        st.info("暂无月份数据")

with tab2:
    st.markdown("### 发票数据分析")
    
    all_invoices = db.get_invoice_records()
    
    if all_invoices:
        df_invoices = pd.DataFrame(all_invoices)
        df_invoices['date'] = pd.to_datetime(df_invoices['date'])
        
        st.markdown("#### 服务商分布")
        
        company_stats = df_invoices.groupby('company').agg({
            'amount': ['count', 'sum', 'mean']
        }).round(2)
        
        company_stats.columns = ['次数', '总金额', '平均金额']
        company_stats = company_stats.reset_index()
        company_stats.columns = ['服务商', '次数', '总金额', '平均金额']
        
        col_chart1, col_chart2 = st.columns([1, 1])
        
        with col_chart1:
            fig_pie = px.pie(
                company_stats,
                values='总金额',
                names='服务商',
                title='各服务商金额占比'
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        
        with col_chart2:
            fig_bar = px.bar(
                company_stats.sort_values('总金额', ascending=True),
                x='总金额',
                y='服务商',
                orientation='h',
                title='各服务商金额对比'
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        
        st.markdown("#### 服务商统计详情")
        
        st.dataframe(
            company_stats.sort_values('总金额', ascending=False),
            use_container_width=True,
            hide_index=True,
            column_config={
                "总金额": st.column_config.NumberColumn("总金额", format="¥%.2f"),
                "平均金额": st.column_config.NumberColumn("平均金额", format="¥%.2f"),
            }
        )
        
        st.markdown("---")
        
        st.markdown("#### 发票金额分布")
        
        fig_hist = px.histogram(
            df_invoices,
            x='amount',
            nbins=20,
            title='发票金额分布直方图',
            labels={'amount': '金额（元）', 'count': '数量'}
        )
        st.plotly_chart(fig_hist, use_container_width=True)
        
    else:
        st.info("暂无发票数据")

with tab3:
    st.markdown("### 导出历史记录")
    
    export_history = db.get_export_history(50)
    
    if export_history:
        df_history = pd.DataFrame(export_history)
        df_history['created_at'] = pd.to_datetime(df_history['created_at'])
        df_history = df_history.sort_values('created_at', ascending=False)
        
        df_display = df_history[['month_folder', 'export_type', 'record_count', 'total_amount', 'created_at']].copy()
        df_display['created_at'] = df_display['created_at'].dt.strftime('%Y-%m-%d %H:%M:%S')
        df_display.columns = ['月份', '类型', '记录数', '总金额', '导出时间']
        
        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "总金额": st.column_config.NumberColumn("总金额", format="¥%.2f"),
            }
        )
        
        st.markdown("---")
        
        st.markdown("#### 导出趋势")
        
        df_history['date'] = df_history['created_at'].dt.date
        daily_exports = df_history.groupby('date').size().reset_index(name='导出次数')
        
        fig_line = px.line(
            daily_exports,
            x='date',
            y='导出次数',
            title='每日导出次数',
            markers=True
        )
        st.plotly_chart(fig_line, use_container_width=True)
        
    else:
        st.info("暂无导出历史记录")

st.markdown("---")

st.markdown("### 📊 综合统计")

col_stat1, col_stat2 = st.columns(2)

with col_stat1:
    st.markdown("#### 报销类型分布")
    
    reimburse_by_type = stats['reimburse_by_type']
    
    if reimburse_by_type:
        df_type = pd.DataFrame([
            {'类型': k, '金额': v}
            for k, v in reimburse_by_type.items()
        ])
        
        fig_type = px.pie(
            df_type,
            values='金额',
            names='类型',
            title='报销类型金额占比'
        )
        st.plotly_chart(fig_type, use_container_width=True)
    else:
        st.info("暂无报销数据")

with col_stat2:
    st.markdown("#### 数据统计摘要")
    
    all_checkin = db.get_checkin_records()
    
    if all_checkin:
        df_checkin = pd.DataFrame(all_checkin)
        df_checkin['work_hours'] = pd.to_numeric(df_checkin['work_hours'])
        
        st.write(f"- **总打卡天数**: {len(df_checkin)} 天")
        st.write(f"- **平均工作时长**: {df_checkin['work_hours'].mean():.1f} 小时")
        st.write(f"- **最长工作时长**: {df_checkin['work_hours'].max():.1f} 小时")
        st.write(f"- **最短工作时长**: {df_checkin['work_hours'].min():.1f} 小时")
        
        config = db.get_config('reimburse_rules') or {
            'night_meal': {
                'dinner_threshold': 9.5,
                'night_threshold': 12
            },
            'taxi': {
                'threshold': 11.0
            }
        }
        
        dinner_threshold = config['night_meal']['dinner_threshold']
        night_threshold = config['night_meal']['night_threshold']
        taxi_threshold = config['taxi']['threshold']
        
        st.write(f"- **符合晚餐报销**: {len(df_checkin[df_checkin['work_hours'] >= dinner_threshold])} 天")
        st.write(f"- **符合夜宵报销**: {len(df_checkin[df_checkin['work_hours'] >= night_threshold])} 天")
        st.write(f"- **符合打车报销**: {len(df_checkin[df_checkin['work_hours'] > taxi_threshold])} 天")
    else:
        st.info("暂无打卡数据")
