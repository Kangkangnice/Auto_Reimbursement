import streamlit as st
import os
import sys
from datetime import datetime, date
import pandas as pd

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SRC_DIR)
sys.path.insert(0, SRC_DIR)

import database as db
import utils

st.set_page_config(
    page_title="数据导入 - 报销管理系统",
    page_icon="📊",
    layout="wide"
)

st.markdown("# 📊 数据导入")
st.markdown("---")

def get_reimburse_month_from_date(date_obj):
    if date_obj.month == 12:
        return f"{str(date_obj.year + 1)[-2:]}_01"
    else:
        return f"{str(date_obj.year)[-2:]}_{str(date_obj.month + 1).zfill(2)}"

def get_expense_month_range(month_folder):
    try:
        year = 2000 + int(month_folder[:2])
        month = int(month_folder[3:5])
        
        expense_month = month - 1
        expense_year = year
        if expense_month == 0:
            expense_month = 12
            expense_year = year - 1
        
        start_date = date(expense_year, expense_month, 1)
        if expense_month == 12:
            end_date = date(expense_year + 1, 1, 1) - pd.Timedelta(days=1)
        else:
            end_date = date(expense_year, expense_month + 1, 1) - pd.Timedelta(days=1)
        
        return start_date, end_date
    except:
        return None, None

def validate_invoice_for_import(invoice_record, month_folder):
    result = {
        'valid': False,
        'reason': ''
    }
    
    start_date, end_date = get_expense_month_range(month_folder)
    if not start_date or not end_date:
        result['reason'] = '无法确定费用月份范围'
        return result
    
    invoice_date = invoice_record.get('date')
    if not invoice_date:
        result['reason'] = '无法提取发票日期'
        return result
    
    if isinstance(invoice_date, datetime):
        invoice_date = invoice_date.date()
    elif isinstance(invoice_date, str):
        try:
            invoice_date = datetime.strptime(invoice_date, '%Y-%m-%d').date()
        except:
            result['reason'] = '日期格式错误'
            return result
    
    if invoice_date < start_date or invoice_date > end_date:
        result['reason'] = f'日期{invoice_date}不在费用月份范围({start_date}~{end_date})'
        return result
    
    result['valid'] = True
    result['reason'] = '符合条件'
    return result

def detect_month_from_checkin_file(file_path):
    try:
        records, _ = utils.parse_checkin_excel(file_path)
        if records:
            dates = [r['date'] for r in records if 'date' in r]
            if dates:
                min_date = min(dates)
                return get_reimburse_month_from_date(min_date)
    except:
        pass
    return None

def detect_month_from_invoice_files(files, temp_dir):
    detected_months = []
    
    for file in files:
        temp_path = utils.save_uploaded_file(file, temp_dir)
        record = utils.parse_taxi_pdf(temp_path)
        
        if record and record.get('date'):
            month = get_reimburse_month_from_date(record['date'])
            detected_months.append(month)
        
        try:
            os.remove(temp_path)
        except:
            pass
    
    if detected_months:
        from collections import Counter
        month_counts = Counter(detected_months)
        return month_counts.most_common(1)[0][0]
    
    return None

st.markdown("### 📤 上传文件")

col_file1, col_file2 = st.columns(2)

with col_file1:
    st.markdown("#### 打卡文件")
    checkin_file = st.file_uploader(
        "选择打卡 Excel 文件",
        type=['xlsx', 'xls'],
        key='checkin_uploader'
    )

with col_file2:
    st.markdown("#### 发票文件")
    invoice_files = st.file_uploader(
        "选择发票 PDF 文件（支持多选）",
        type=['pdf'],
        accept_multiple_files=True,
        key='invoice_uploader'
    )

st.markdown("---")

st.markdown("### 📁 月份识别")

auto_detected_month = None
detection_source = None

temp_dir = os.path.join(PROJECT_ROOT, 'temp')
os.makedirs(temp_dir, exist_ok=True)

if checkin_file is not None:
    temp_path = utils.save_uploaded_file(checkin_file, temp_dir)
    detected = detect_month_from_checkin_file(temp_path)
    if detected:
        auto_detected_month = detected
        detection_source = "打卡文件"
    try:
        os.remove(temp_path)
    except:
        pass

if invoice_files and auto_detected_month is None:
    detected = detect_month_from_invoice_files(invoice_files, temp_dir)
    if detected:
        auto_detected_month = detected
        detection_source = "发票文件"

col_month1, col_month2, col_month3 = st.columns([1, 1, 1])

with col_month1:
    if auto_detected_month:
        st.success(f"🔍 自动识别月份: **{auto_detected_month}** (来源: {detection_source})")
        st.session_state['auto_month'] = auto_detected_month
    else:
        st.info("📅 请上传文件以自动识别月份")

with col_month2:
    st.markdown("**手动设置月份：**")
    
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        default_year = str(datetime.now().year)[-2:]
        year_input = st.text_input("年份", value=default_year, max_chars=2, key='manual_year')
    with col_m2:
        default_month = str(datetime.now().month).zfill(2)
        month_input = st.text_input("月份", value=default_month, max_chars=2, key='manual_month')
    
    manual_month = f"{year_input}_{month_input}"

with col_month3:
    st.markdown("**最终使用月份：**")
    
    use_auto = st.checkbox("使用自动识别月份", value=True, key='use_auto_month')
    
    if use_auto and auto_detected_month:
        final_month = auto_detected_month
    else:
        final_month = manual_month
    
    if utils.validate_month_folder_name(final_month):
        st.markdown(f"### 📂 **{final_month}**")
        st.session_state['current_month'] = final_month
    else:
        st.error("月份格式不正确")

st.markdown("---")

current_month = st.session_state.get('current_month', manual_month)

st.markdown("### 📥 导入数据")

col_import1, col_import2 = st.columns(2)

with col_import1:
    st.markdown("#### 打卡数据导入")
    
    if checkin_file is not None:
        st.info(f"文件: {checkin_file.name}")
        
        if st.button("解析并导入打卡数据", type="primary", key='import_checkin_btn'):
            with st.spinner("正在解析打卡文件..."):
                temp_path = utils.save_uploaded_file(checkin_file, temp_dir)
                
                records, error = utils.parse_checkin_excel(temp_path)
                
                if records:
                    db.save_checkin_records(records, current_month, checkin_file.name)
                    st.success(f"成功导入 {len(records)} 条打卡记录到 {current_month}！")
                    
                    with st.expander("查看导入数据预览"):
                        df = pd.DataFrame(records)
                        df['date'] = df['date'].apply(lambda x: x.strftime('%Y-%m-%d') if hasattr(x, 'strftime') else str(x))
                        st.dataframe(df, use_container_width=True, hide_index=True)
                else:
                    st.error(f"导入失败: {error}")
                
                try:
                    os.remove(temp_path)
                except:
                    pass
    else:
        st.info("请先上传打卡文件")

with col_import2:
    st.markdown("#### 发票数据导入（自动校验）")
    
    start_date, end_date = get_expense_month_range(current_month)
    expense_month_str = f"{start_date} ~ {end_date}" if start_date else "未知"
    st.caption(f"费用月份范围: {expense_month_str}")
    
    if invoice_files:
        st.info(f"已选择 {len(invoice_files)} 个文件")
        
        if st.button("解析并导入发票数据", type="primary", key='import_invoice_btn'):
            with st.spinner("正在解析和校验发票文件..."):
                valid_records = []
                invalid_records = []
                parse_failed = 0
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for i, file in enumerate(invoice_files):
                    status_text.text(f"正在处理: {file.name}")
                    progress_bar.progress((i + 1) / len(invoice_files))
                    
                    temp_path = utils.save_uploaded_file(file, temp_dir)
                    
                    record = utils.parse_taxi_pdf(temp_path)
                    
                    if record and record.get('amount', 0) > 0:
                        record['source_file'] = file.name
                        
                        validation = validate_invoice_for_import(record, current_month)
                        
                        if validation['valid']:
                            valid_records.append(record)
                        else:
                            record['invalid_reason'] = validation['reason']
                            invalid_records.append(record)
                    else:
                        parse_failed += 1
                    
                    try:
                        os.remove(temp_path)
                    except:
                        pass
                
                progress_bar.empty()
                status_text.empty()
                
                if valid_records:
                    db.save_invoice_records(valid_records, current_month)
                    st.success(f"✅ 成功导入 {len(valid_records)} 条符合条件的发票记录！")
                
                if invalid_records:
                    st.warning(f"⚠️ {len(invalid_records)} 条记录不符合条件，未导入")
                    with st.expander("查看不符合条件的记录"):
                        df_invalid = pd.DataFrame([{
                            '日期': r.get('date', ''),
                            '金额': r.get('amount', 0),
                            '原因': r.get('invalid_reason', '')
                        } for r in invalid_records])
                        st.dataframe(df_invalid, use_container_width=True, hide_index=True)
                
                if parse_failed > 0:
                    st.error(f"❌ {parse_failed} 个文件解析失败")
                
                if valid_records:
                    with st.expander("查看已导入数据预览"):
                        df = pd.DataFrame(valid_records)
                        df['date'] = df['date'].apply(lambda x: x.strftime('%Y-%m-%d') if hasattr(x, 'strftime') else str(x))
                        st.dataframe(df, use_container_width=True, hide_index=True)
                
                if not valid_records and not invalid_records:
                    st.error("所有文件解析失败，请检查文件格式")
    else:
        st.info("请先上传发票文件")

st.markdown("---")

st.markdown("### 📊 当前月份数据概览")

st.markdown(f"**当前月份: {current_month}**")

col1, col2 = st.columns(2)

with col1:
    st.markdown("#### 打卡记录")
    checkin_records = db.get_checkin_records(current_month)
    if checkin_records:
        df_checkin = pd.DataFrame(checkin_records)
        df_checkin['date'] = pd.to_datetime(df_checkin['date']).dt.strftime('%Y-%m-%d')
        df_checkin = df_checkin[['date', 'work_hours', 'source_file']]
        df_checkin.columns = ['日期', '工作时长', '来源文件']
        st.dataframe(df_checkin, use_container_width=True, hide_index=True)
        st.info(f"共 {len(checkin_records)} 条记录")
    else:
        st.info("暂无打卡记录")

with col2:
    st.markdown("#### 发票记录")
    invoice_records = db.get_invoice_records(current_month)
    if invoice_records:
        df_invoice = pd.DataFrame(invoice_records)
        df_invoice['date'] = pd.to_datetime(df_invoice['date']).dt.strftime('%Y-%m-%d')
        df_invoice = df_invoice[['date', 'amount', 'company', 'source_file']]
        df_invoice.columns = ['日期', '金额', '服务商', '来源文件']
        st.dataframe(df_invoice, use_container_width=True, hide_index=True)
        st.info(f"共 {len(invoice_records)} 条记录，总金额: ¥{sum(r['amount'] for r in invoice_records):.2f}")
    else:
        st.info("暂无发票记录")

st.markdown("---")

st.markdown("### 🗑️ 数据管理")

col_del1, col_del2, col_del3 = st.columns([1, 1, 2])

with col_del1:
    if st.button("清空当前月份数据", type="secondary", key='clear_data_btn'):
        st.session_state['confirm_delete'] = True

with col_del2:
    if st.session_state.get('confirm_delete', False):
        if st.button("确认删除", type="primary", key='confirm_delete_btn'):
            db.clear_month_data(current_month)
            st.success(f"已清空 {current_month} 的所有数据")
            st.session_state['confirm_delete'] = False
            st.rerun()

if st.session_state.get('confirm_delete', False):
    st.warning("⚠️ 确认要清空当前月份的所有数据吗？此操作不可恢复！")

st.markdown("---")

st.markdown("### 🔧 数据校验与清理")

if st.button("🔍 检查不符合条件的发票记录", key='check_invalid_btn'):
    invoice_records = db.get_invoice_records(current_month)
    checkin_records = db.get_checkin_records(current_month)
    
    config = db.get_config('reimburse_rules') or {'taxi': {'threshold': 11.0}}
    taxi_threshold = config['taxi']['threshold']
    
    invalid_records = []
    
    for invoice in invoice_records:
        invoice_date_str = invoice['date'] if isinstance(invoice['date'], str) else invoice['date'].strftime('%Y-%m-%d')
        
        start_date, end_date = get_expense_month_range(current_month)
        
        try:
            invoice_date = datetime.strptime(invoice_date_str, '%Y-%m-%d').date()
        except:
            invalid_records.append({
                'id': invoice['id'],
                'date': invoice_date_str,
                'amount': invoice['amount'],
                'reason': '日期格式错误'
            })
            continue
        
        if start_date and end_date:
            if invoice_date < start_date or invoice_date > end_date:
                invalid_records.append({
                    'id': invoice['id'],
                    'date': invoice_date_str,
                    'amount': invoice['amount'],
                    'reason': f'日期不在费用月份范围({start_date}~{end_date})'
                })
                continue
        
        matching_checkin = None
        for checkin in checkin_records:
            checkin_date_str = checkin['date'] if isinstance(checkin['date'], str) else checkin['date'].strftime('%Y-%m-%d')
            if checkin_date_str == invoice_date_str:
                matching_checkin = checkin
                break
        
        if not matching_checkin:
            invalid_records.append({
                'id': invoice['id'],
                'date': invoice_date_str,
                'amount': invoice['amount'],
                'reason': '无对应打卡记录'
            })
            continue
        
        work_hours = matching_checkin['work_hours']
        if work_hours < taxi_threshold:
            invalid_records.append({
                'id': invoice['id'],
                'date': invoice_date_str,
                'amount': invoice['amount'],
                'reason': f'工作时长{work_hours}h未达到{taxi_threshold}h阈值'
            })
    
    if invalid_records:
        st.warning(f"发现 {len(invalid_records)} 条不符合条件的发票记录")
        
        df_invalid = pd.DataFrame(invalid_records)
        df_invalid = df_invalid[['date', 'amount', 'reason']]
        df_invalid.columns = ['日期', '金额', '原因']
        st.dataframe(df_invalid, use_container_width=True, hide_index=True)
        
        st.session_state['invalid_invoice_ids'] = [r['id'] for r in invalid_records]
        
        if st.button("🗑️ 删除所有不符合条件的记录", type="primary", key='delete_invalid_btn'):
            for record_id in st.session_state['invalid_invoice_ids']:
                db.delete_invoice_record(record_id)
            st.success(f"已删除 {len(st.session_state['invalid_invoice_ids'])} 条不符合条件的记录")
            st.session_state['invalid_invoice_ids'] = []
            st.rerun()
    else:
        st.success("✅ 所有发票记录都符合条件！")

st.markdown("---")

st.markdown("### 📋 文件要求说明")
st.markdown("""
| 文件类型 | 格式要求 | 说明 |
|---------|---------|------|
| 打卡文件 | Excel (.xlsx/.xls) | 需包含工作时长列，文件名建议含"打卡" |
| 发票文件 | PDF | **行程单 + 发票单** 需同时上传，支持批量上传 |

**发票导入校验规则：**
- 发票日期必须在费用月份范围内（报销月份 - 1）
- 例如：报销月份 `25_05`，则发票日期应在 2025年4月
- 不符合条件的发票将不会导入

**打车报销条件（导出时校验）：**
- 发票日期必须有对应的打卡记录
- 该日期工作时长 ≥ 打车报销阈值（默认11小时）

**月份识别规则：**
- 系统自动从文件中提取日期，计算报销月份（费用月份 + 1）
- 例如：费用发生在 2025年4月，则报销月份为 `25_05`
- 可手动切换使用自动识别或手动设置的月份
""")
