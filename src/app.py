import streamlit as st
import os
import sys

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SRC_DIR)
sys.path.insert(0, SRC_DIR)

import database as db

db.init_db()

st.set_page_config(
    page_title="报销管理系统",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
    }
    .metric-value {
        font-size: 2rem;
        font-weight: bold;
        color: #1f77b4;
    }
    .metric-label {
        font-size: 0.9rem;
        color: #666;
    }
    [data-testid="stSidebarHeader"] {
        display: none;
    }
    [data-testid="stSidebar"]::before {
        content: "报销管理系统";
        display: block;
        font-size: 1.5rem;
        font-weight: bold;
        color: #1f77b4;
        padding: 1rem;
        text-align: center;
        border-bottom: 1px solid #e0e0e0;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<h1 class="main-header">💰 报销管理系统</h1>', unsafe_allow_html=True)

st.markdown("### 系统功能")
st.markdown("""
本系统用于自动处理加班打车和夜宵晚餐报销，主要功能包括：

- 📊 **数据导入**：上传打卡 Excel 和发票 PDF 文件
- 📝 **数据预览**：查看和编辑已导入的数据
- ⚙️ **配置管理**：调整报销阈值和金额设置
- 📈 **统计分析**：查看报销统计和历史记录
- 📥 **导出下载**：生成并下载报销明细表
""")

st.markdown("---")

st.markdown("### 数据概览")

stats = db.get_statistics()

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.markdown(f'<div class="metric-value">{stats["total_checkin_records"]}</div>', unsafe_allow_html=True)
    st.markdown('<div class="metric-label">打卡记录数</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.markdown(f'<div class="metric-value">{stats["total_invoice_records"]}</div>', unsafe_allow_html=True)
    st.markdown('<div class="metric-label">发票记录数</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

with col3:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.markdown(f'<div class="metric-value">¥{stats["total_invoice_amount"]:.2f}</div>', unsafe_allow_html=True)
    st.markdown('<div class="metric-label">发票总金额</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

with col4:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.markdown(f'<div class="metric-value">{stats["total_exports"]}</div>', unsafe_allow_html=True)
    st.markdown('<div class="metric-label">导出次数</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("---")

st.markdown("### 快速开始")

col_left, col_right = st.columns(2)

with col_left:
    st.markdown("#### 📋 使用步骤")
    st.markdown("""
    1. 点击左侧菜单 **📊 数据导入**
    2. 选择月份文件夹名称（如 `25_05`）
    3. 上传打卡 Excel 文件
    4. 上传发票 PDF 文件
    5. 点击 **📝 数据预览** 检查数据
    6. 点击 **📥 导出下载** 生成报表
    """)

with col_right:
    st.markdown("#### ⚠️ 注意事项")
    st.markdown("""
    - 打卡文件需包含 **工作时长** 列
    - 发票文件需为高德打车 **行程单** PDF
    - 月份文件夹格式：`YY_MM`（如 `25_05`）
    - 可在 **⚙️ 配置管理** 调整报销规则
    """)

st.markdown("---")

st.markdown("### 最近导出记录")

export_history = db.get_export_history(5)

if export_history:
    import pandas as pd
    df_history = pd.DataFrame(export_history)
    df_history['created_at'] = pd.to_datetime(df_history['created_at']).dt.strftime('%Y-%m-%d %H:%M')
    df_history = df_history[['month_folder', 'export_type', 'record_count', 'total_amount', 'created_at']]
    df_history.columns = ['月份', '类型', '记录数', '总金额', '导出时间']
    st.dataframe(df_history, use_container_width=True, hide_index=True)
else:
    st.info("暂无导出记录")

st.markdown("---")

st.markdown("""
<div style="text-align: center; color: #666; font-size: 0.8rem;">
    报销管理系统 v1.0 | 基于 Streamlit 构建
</div>
""", unsafe_allow_html=True)
