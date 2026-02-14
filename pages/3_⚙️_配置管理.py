import streamlit as st
import os
import sys
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database as db

st.set_page_config(
    page_title="配置管理 - 报销管理系统",
    page_icon="⚙️",
    layout="wide"
)

st.markdown("# ⚙️ 配置管理")
st.markdown("---")

tab1, tab2, tab3 = st.tabs(["💰 报销规则", "📝 输出设置", "📁 文件路径"])

with tab1:
    st.markdown("### 报销规则配置")
    
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
    
    st.markdown("#### 晚餐报销设置")
    
    col1, col2 = st.columns(2)
    
    with col1:
        dinner_threshold = st.number_input(
            "晚餐报销阈值（小时）",
            min_value=0.0,
            max_value=24.0,
            value=float(config['night_meal']['dinner_threshold']),
            step=0.5,
            help="工作时长达到此阈值可报销晚餐"
        )
    
    with col2:
        dinner_amount = st.number_input(
            "晚餐报销金额（元）",
            min_value=0,
            max_value=100,
            value=int(config['night_meal']['dinner_amount']),
            step=1,
            help="晚餐报销的标准金额"
        )
    
    st.markdown("#### 夜宵报销设置")
    
    col3, col4 = st.columns(2)
    
    with col3:
        night_threshold = st.number_input(
            "夜宵报销阈值（小时）",
            min_value=0.0,
            max_value=24.0,
            value=float(config['night_meal']['night_threshold']),
            step=0.5,
            help="工作时长达到此阈值可报销夜宵"
        )
    
    with col4:
        night_amount = st.number_input(
            "夜宵报销金额（元）",
            min_value=0,
            max_value=100,
            value=int(config['night_meal']['night_amount']),
            step=1,
            help="夜宵报销的标准金额"
        )
    
    st.markdown("#### 打车报销设置")
    
    taxi_threshold = st.number_input(
        "打车报销阈值（小时）",
        min_value=0.0,
        max_value=24.0,
        value=float(config['taxi']['threshold']),
        step=0.5,
        help="工作时长超过此阈值可报销打车费用"
    )
    
    st.markdown("---")
    
    col_save, col_reset = st.columns([1, 1])
    
    with col_save:
        if st.button("💾 保存报销规则", type="primary", use_container_width=True):
            new_config = {
                'night_meal': {
                    'dinner_threshold': dinner_threshold,
                    'dinner_amount': dinner_amount,
                    'night_threshold': night_threshold,
                    'night_amount': night_amount
                },
                'taxi': {
                    'threshold': taxi_threshold
                }
            }
            db.set_config('reimburse_rules', new_config)
            st.success("报销规则已保存！")
    
    with col_reset:
        if st.button("🔄 恢复默认值", type="secondary", use_container_width=True):
            default_config = {
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
            db.set_config('reimburse_rules', default_config)
            st.success("已恢复默认值！")
            st.rerun()
    
    st.markdown("---")
    
    st.markdown("### 📋 当前规则说明")
    
    st.info(f"""
    **晚餐报销规则：**
    - 工作时长 ≥ {dinner_threshold} 小时，可报销 ¥{dinner_amount}
    
    **夜宵报销规则：**
    - 工作时长 ≥ {night_threshold} 小时，可报销 ¥{night_amount}
    - 注意：达到夜宵阈值时，晚餐和夜宵可同时报销
    
    **打车报销规则：**
    - 工作时长 > {taxi_threshold} 小时，可报销打车费用
    - 打车金额按实际发票金额计算
    """)

with tab2:
    st.markdown("### 输出设置配置")
    
    output_config = db.get_config('output') or {
        'default_name': '刘明康',
        'night_meal_template': '{name}_晚餐、夜宵报销明细表_{month}月.xls',
        'taxi_template': '{name}_加班打车报销明细表_{month}月.xls'
    }
    
    st.markdown("#### 基本信息设置")
    
    default_name = st.text_input(
        "默认姓名",
        value=output_config['default_name'],
        help="报销明细表中的默认姓名"
    )
    
    st.markdown("#### 文件命名模板")
    
    st.markdown("""
    **可用变量说明：**
    - `{name}` - 姓名
    - `{month}` - 月份（两位数字）
    """)
    
    night_meal_template = st.text_input(
        "夜宵晚餐报销明细模板",
        value=output_config['night_meal_template'],
        help="夜宵晚餐报销明细表的文件名模板"
    )
    
    taxi_template = st.text_input(
        "打车报销明细模板",
        value=output_config['taxi_template'],
        help="打车报销明细表的文件名模板"
    )
    
    st.markdown("---")
    
    st.markdown("#### 文件名预览")
    
    col_preview1, col_preview2 = st.columns(2)
    
    with col_preview1:
        preview_name = night_meal_template.format(name=default_name, month="05")
        st.code(preview_name, language=None)
        st.caption("夜宵晚餐报销明细表示例")
    
    with col_preview2:
        preview_name = taxi_template.format(name=default_name, month="05")
        st.code(preview_name, language=None)
        st.caption("打车报销明细表示例")
    
    st.markdown("---")
    
    if st.button("💾 保存输出设置", type="primary"):
        new_output_config = {
            'default_name': default_name,
            'night_meal_template': night_meal_template,
            'taxi_template': taxi_template
        }
        db.set_config('output', new_output_config)
        st.success("输出设置已保存！")

with tab3:
    st.markdown("### 文件路径配置")
    
    file_config = db.get_config('file_paths') or {
        'month_folder_pattern': '\\d{2}_\\d{2}',
        'checkin_file_pattern': '打卡',
        'invoice_folder_name': '发票'
    }
    
    st.markdown("#### 文件夹命名规则")
    
    month_folder_pattern = st.text_input(
        "月份文件夹正则表达式",
        value=file_config['month_folder_pattern'],
        help="用于匹配月份文件夹名称的正则表达式"
    )
    
    st.markdown("#### 文件识别规则")
    
    col_file1, col_file2 = st.columns(2)
    
    with col_file1:
        checkin_file_pattern = st.text_input(
            "打卡文件识别关键词",
            value=file_config['checkin_file_pattern'],
            help="文件名包含此关键词的文件将被识别为打卡文件"
        )
    
    with col_file2:
        invoice_folder_name = st.text_input(
            "发票文件夹名称",
            value=file_config['invoice_folder_name'],
            help="存放发票文件的子文件夹名称"
        )
    
    st.markdown("---")
    
    st.markdown("### 📋 配置说明")
    
    st.info(f"""
    **月份文件夹格式：**
    - 正则表达式：`{month_folder_pattern}`
    - 示例：`25_05` 表示 2025年5月
    
    **打卡文件识别：**
    - 文件名包含 "{checkin_file_pattern}" 的 Excel 文件
    - 示例：`上下班打卡_日报_202505.xlsx`
    
    **发票文件夹：**
    - 发票文件应放在月份文件夹下的 "{invoice_folder_name}" 子文件夹中
    - 示例：`25_05/发票/高德打车电子行程单.pdf`
    """)
    
    st.markdown("---")
    
    if st.button("💾 保存文件路径配置", type="primary"):
        new_file_config = {
            'month_folder_pattern': month_folder_pattern,
            'checkin_file_pattern': checkin_file_pattern,
            'invoice_folder_name': invoice_folder_name
        }
        db.set_config('file_paths', new_file_config)
        st.success("文件路径配置已保存！")

st.markdown("---")

st.markdown("### 📤 导出/导入配置")

col_export, col_import = st.columns(2)

with col_export:
    st.markdown("#### 导出配置")
    
    all_config = db.get_all_config()
    
    if st.button("📥 导出配置到文件"):
        import io
        config_json = json.dumps(all_config, ensure_ascii=False, indent=2)
        
        st.download_button(
            label="下载配置文件",
            data=config_json,
            file_name="reimburse_config.json",
            mime="application/json"
        )

with col_import:
    st.markdown("#### 导入配置")
    
    uploaded_config = st.file_uploader(
        "选择配置文件",
        type=['json'],
        key='config_uploader'
    )
    
    if uploaded_config is not None:
        if st.button("📤 导入配置"):
            try:
                imported_config = json.load(uploaded_config)
                
                for key, value in imported_config.items():
                    db.set_config(key, value)
                
                st.success("配置导入成功！")
                st.rerun()
            except Exception as e:
                st.error(f"导入失败: {str(e)}")
