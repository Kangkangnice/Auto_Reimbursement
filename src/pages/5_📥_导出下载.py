import streamlit as st
import os
import sys
import pandas as pd
import xlwt
import zipfile
from io import BytesIO
from datetime import datetime, date

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SRC_DIR)
sys.path.insert(0, SRC_DIR)

import database as db
import utils

DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
UPLOADS_DIR = os.path.join(DATA_DIR, 'uploads')
OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'output')

st.set_page_config(
    page_title="导出下载 - 报销管理系统",
    page_icon="📥",
    layout="wide"
)

st.markdown("# 📥 导出下载")
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

def validate_taxi_invoice(invoice_record, checkin_records, month_folder):
    result = {
        'valid': False,
        'reason': '',
        'work_hours': 0
    }
    
    config = db.get_config('reimburse_rules') or {'taxi': {'threshold': 11.0}}
    taxi_threshold = config['taxi']['threshold']
    
    start_date, end_date = get_expense_month_range(month_folder)
    if not start_date or not end_date:
        result['reason'] = '无法确定费用月份范围'
        return result
    
    invoice_date_str = invoice_record['date'] if isinstance(invoice_record['date'], str) else invoice_record['date'].strftime('%Y-%m-%d')
    try:
        invoice_date = datetime.strptime(invoice_date_str, '%Y-%m-%d').date()
    except:
        result['reason'] = '发票日期格式错误'
        return result
    
    if invoice_date < start_date or invoice_date > end_date:
        result['reason'] = f'日期不在费用月份范围内({start_date.strftime("%Y-%m-%d")}~{end_date.strftime("%Y-%m-%d")})'
        return result
    
    matching_checkin = None
    for checkin in checkin_records:
        checkin_date_str = checkin['date'] if isinstance(checkin['date'], str) else checkin['date'].strftime('%Y-%m-%d')
        try:
            checkin_date = datetime.strptime(checkin_date_str, '%Y-%m-%d').date()
            if checkin_date == invoice_date:
                matching_checkin = checkin
                break
        except:
            continue
    
    if not matching_checkin:
        result['reason'] = '无对应打卡记录'
        return result
    
    work_hours = matching_checkin['work_hours']
    result['work_hours'] = work_hours
    
    if work_hours < taxi_threshold:
        result['reason'] = f'工作时长{work_hours}h未达到{taxi_threshold}h阈值'
        return result
    
    result['valid'] = True
    result['reason'] = f'工作时长{work_hours}h，符合条件'
    return result

def generate_night_meal_excel(checkin_records, month_folder):
    output = BytesIO()
    workbook = xlwt.Workbook(encoding='utf-8')
    worksheet = workbook.add_sheet('晚餐夜宵报销')
    
    for i in range(4):
        worksheet.col(i).width = 256 * 20
    
    config = db.get_config('reimburse_rules') or {
        'night_meal': {
            'dinner_threshold': 9.5,
            'dinner_amount': 18,
            'night_threshold': 12,
            'night_amount': 20
        }
    }
    
    dinner_threshold = config['night_meal']['dinner_threshold']
    dinner_amount = config['night_meal']['dinner_amount']
    night_threshold = config['night_meal']['night_threshold']
    night_amount = config['night_meal']['night_amount']
    
    output_config = db.get_config('output') or {'default_name': '姓名'}
    default_name = output_config['default_name']
    
    worksheet.write(0, 0, '晚餐、夜宵报销明细')
    
    worksheet.write(1, 0, '月份')
    worksheet.write(1, 1, '日期')
    worksheet.write(1, 2, f'晚餐报销{dinner_amount}元（工作时长{dinner_threshold}小时）')
    worksheet.write(1, 3, f'夜宵报销{night_amount}元（工作时长{night_threshold}小时）')
    
    row = 2
    total_dinner = 0
    total_night = 0
    
    eligible_records = []
    
    for record in checkin_records:
        work_hours = record['work_hours']
        
        if work_hours >= dinner_threshold:
            eligible_records.append(record)
            
            date_str = record['date'] if isinstance(record['date'], str) else record['date'].strftime('%Y-%m-%d')
            
            try:
                dt = datetime.strptime(date_str, '%Y-%m-%d')
                month_str = dt.strftime('%m月')
                weekday_map = {0: '星期一', 1: '星期二', 2: '星期三', 3: '星期四', 4: '星期五', 5: '星期六', 6: '星期日'}
                weekday_str = weekday_map[dt.weekday()]
                date_display = f"{dt.strftime('%Y/%m/%d')} {weekday_str}"
            except:
                month_str = month_folder[-2:] + '月'
                date_display = date_str
            
            worksheet.write(row, 0, month_str)
            worksheet.write(row, 1, date_display)
            
            if work_hours >= night_threshold:
                worksheet.write(row, 2, dinner_amount)
                worksheet.write(row, 3, night_amount)
                total_dinner += dinner_amount
                total_night += night_amount
            else:
                worksheet.write(row, 2, dinner_amount)
                worksheet.write(row, 3, '')
                total_dinner += dinner_amount
            
            row += 1
    
    total_all = total_dinner + total_night
    worksheet.write(row, 0, '')
    worksheet.write(row, 1, '合计')
    worksheet.write(row, 2, total_dinner)
    worksheet.write(row, 3, total_night)
    
    row += 1
    worksheet.write(row, 0, '')
    worksheet.write(row, 1, '最终总计')
    worksheet.write(row, 2, '')
    worksheet.write(row, 3, total_all)
    
    workbook.save(output)
    output.seek(0)
    
    return output, len(eligible_records), total_all

def generate_taxi_excel(validated_records, month_folder):
    output = BytesIO()
    workbook = xlwt.Workbook(encoding='utf-8')
    worksheet = workbook.add_sheet('加班打车报销')
    
    for i in range(7):
        worksheet.col(i).width = 256 * 15
    
    config = db.get_config('reimburse_rules') or {'taxi': {'threshold': 11.0}}
    taxi_threshold = config['taxi']['threshold']
    
    output_config = db.get_config('output') or {'default_name': '姓名'}
    default_name = output_config['default_name']
    
    worksheet.write(0, 0, f'打车报销明细（工作时长≥{taxi_threshold}小时）')
    
    worksheet.write(1, 0, '月份')
    worksheet.write(1, 1, '日期')
    worksheet.write(1, 2, '出发地')
    worksheet.write(1, 3, '到达地')
    worksheet.write(1, 4, '金额')
    worksheet.write(1, 5, '工作时长')
    
    row = 2
    total_amount = 0
    
    for record in validated_records:
        invoice = record['invoice']
        work_hours = record['work_hours']
        
        date_str = invoice['date'] if isinstance(invoice['date'], str) else invoice['date'].strftime('%Y-%m-%d')
        
        try:
            dt = datetime.strptime(date_str, '%Y-%m-%d')
            month_str = dt.strftime('%m月')
            date_display = dt.strftime('%Y-%m-%d')
        except:
            month_str = month_folder[-2:] + '月'
            date_display = date_str
        
        worksheet.write(row, 0, month_str)
        worksheet.write(row, 1, date_display)
        worksheet.write(row, 2, invoice.get('start_location', ''))
        worksheet.write(row, 3, invoice.get('end_location', ''))
        worksheet.write(row, 4, invoice['amount'])
        worksheet.write(row, 5, f'{work_hours:.1f}h')
        
        total_amount += invoice['amount']
        row += 1
    
    worksheet.write(row, 0, '合计')
    worksheet.write(row, 1, '')
    worksheet.write(row, 2, '')
    worksheet.write(row, 3, '')
    worksheet.write(row, 4, total_amount)
    worksheet.write(row, 5, '')
    
    workbook.save(output)
    output.seek(0)
    
    return output, len(validated_records), total_amount

def create_night_meal_zip(excel_data, month_folder, file_name):
    zip_buffer = BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(file_name, excel_data.getvalue())
        
        month_upload_dir = os.path.join(UPLOADS_DIR, month_folder)
        
        if os.path.exists(month_upload_dir):
            for file in os.listdir(month_upload_dir):
                if '打卡' in file and (file.endswith('.xlsx') or file.endswith('.xls')):
                    file_path = os.path.join(month_upload_dir, file)
                    with open(file_path, 'rb') as f:
                        zf.writestr(f"附件/{file}", f.read())
    
    zip_buffer.seek(0)
    return zip_buffer

def create_taxi_zip(excel_data, month_folder, file_name, validated_records):
    zip_buffer = BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(file_name, excel_data.getvalue())
        
        month_upload_dir = os.path.join(UPLOADS_DIR, month_folder)
        
        if os.path.exists(month_upload_dir):
            added_files = set()
            
            for record in validated_records:
                invoice = record['invoice']
                source_file = invoice.get('source_file', '')
                if not source_file:
                    continue
                
                if source_file in added_files:
                    continue
                
                file_path = os.path.join(month_upload_dir, source_file)
                if os.path.exists(file_path):
                    with open(file_path, 'rb') as f:
                        zf.writestr(f"附件/{source_file}", f.read())
                    added_files.add(source_file)
                    
                    if '行程单' in source_file:
                        invoice_file = source_file.replace('行程单', '发票')
                        invoice_path = os.path.join(month_upload_dir, invoice_file)
                        if os.path.exists(invoice_path) and invoice_file not in added_files:
                            with open(invoice_path, 'rb') as f:
                                zf.writestr(f"附件/{invoice_file}", f.read())
                            added_files.add(invoice_file)
                    
                    elif '发票' in source_file:
                        itinerary_file = source_file.replace('发票', '行程单')
                        itinerary_path = os.path.join(month_upload_dir, itinerary_file)
                        if os.path.exists(itinerary_path) and itinerary_file not in added_files:
                            with open(itinerary_path, 'rb') as f:
                                zf.writestr(f"附件/{itinerary_file}", f.read())
                            added_files.add(itinerary_file)
    
    zip_buffer.seek(0)
    return zip_buffer

tab1, tab2 = st.tabs(["🍽️ 晚餐夜宵报销", "🚗 打车报销"])

with tab1:
    st.markdown("### 晚餐夜宵报销明细")
    
    config = db.get_config('reimburse_rules') or {
        'night_meal': {
            'dinner_threshold': 9.5,
            'dinner_amount': 18,
            'night_threshold': 12,
            'night_amount': 20
        }
    }
    
    dinner_threshold = config['night_meal']['dinner_threshold']
    night_threshold = config['night_meal']['night_threshold']
    
    eligible_count = sum(1 for r in checkin_records if r['work_hours'] >= dinner_threshold)
    night_count = sum(1 for r in checkin_records if r['work_hours'] >= night_threshold)
    
    st.info(f"""
    **报销规则说明：**
    - 工作时长 ≥ {dinner_threshold} 小时：可报销晚餐 ¥{config['night_meal']['dinner_amount']}
    - 工作时长 ≥ {night_threshold} 小时：可报销晚餐+夜宵 ¥{config['night_meal']['dinner_amount'] + config['night_meal']['night_amount']}
    
    **当前月份符合条件：**
    - 符合晚餐报销：{eligible_count} 天
    - 符合夜宵报销：{night_count} 天
    """)
    
    if checkin_records:
        st.markdown("#### 数据预览")
        
        preview_data = []
        for record in checkin_records:
            work_hours = record['work_hours']
            if work_hours >= dinner_threshold:
                date_str = record['date'] if isinstance(record['date'], str) else record['date'].strftime('%Y-%m-%d')
                
                dinner_eligible = work_hours >= dinner_threshold
                night_eligible = work_hours >= night_threshold
                
                preview_data.append({
                    '日期': date_str,
                    '工作时长': f"{work_hours:.1f}h",
                    '晚餐': '✅' if dinner_eligible else '❌',
                    '夜宵': '✅' if night_eligible else '❌',
                    '晚餐金额': config['night_meal']['dinner_amount'] if dinner_eligible else 0,
                    '夜宵金额': config['night_meal']['night_amount'] if night_eligible else 0
                })
        
        if preview_data:
            df_preview = pd.DataFrame(preview_data)
            st.dataframe(df_preview, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        col_gen, col_down, col_zip = st.columns([1, 1, 1])
        
        with col_gen:
            if st.button("📊 生成报销明细", type="primary", use_container_width=True, key='gen_night_meal'):
                excel_data, record_count, total_amount = generate_night_meal_excel(checkin_records, selected_month)
                
                st.session_state['night_meal_excel'] = excel_data
                st.session_state['night_meal_count'] = record_count
                st.session_state['night_meal_amount'] = total_amount
                
                st.success(f"生成成功！共 {record_count} 条记录，总金额 ¥{total_amount}")
        
        with col_down:
            if 'night_meal_excel' in st.session_state:
                output_config = db.get_config('output') or {'default_name': '姓名'}
                default_name = output_config['default_name']
                month_num = selected_month[-2:]
                file_name = f"{default_name}_晚餐、夜宵报销明细表_{month_num}月.xls"
                
                st.download_button(
                    label="📥 下载明细表",
                    data=st.session_state['night_meal_excel'],
                    file_name=file_name,
                    mime="application/vnd.ms-excel",
                    use_container_width=True,
                    key='download_night_meal'
                )
        
        with col_zip:
            if 'night_meal_excel' in st.session_state:
                output_config = db.get_config('output') or {'default_name': '姓名'}
                default_name = output_config['default_name']
                month_num = selected_month[-2:]
                file_name = f"{default_name}_晚餐、夜宵报销明细表_{month_num}月.xls"
                zip_name = f"{default_name}_晚餐夜宵报销_{month_num}月.zip"
                
                if st.button("📦 打包下载(含打卡文件)", use_container_width=True, key='zip_night_meal'):
                    zip_data = create_night_meal_zip(
                        st.session_state['night_meal_excel'],
                        selected_month,
                        file_name
                    )
                    st.session_state['night_meal_zip'] = zip_data
                    st.session_state['night_meal_zip_name'] = zip_name
                
                if 'night_meal_zip' in st.session_state:
                    st.download_button(
                        label=f"📥 下载 {st.session_state['night_meal_zip_name']}",
                        data=st.session_state['night_meal_zip'],
                        file_name=st.session_state['night_meal_zip_name'],
                        mime="application/zip",
                        use_container_width=True,
                        key='download_night_meal_zip'
                    )
    else:
        st.warning("该月份暂无打卡记录")

with tab2:
    st.markdown("### 打车报销明细")
    
    config = db.get_config('reimburse_rules') or {'taxi': {'threshold': 11.0}}
    taxi_threshold = config['taxi']['threshold']
    
    start_date, end_date = get_expense_month_range(selected_month)
    expense_month_str = f"{start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}" if start_date else "未知"
    
    validated_records = []
    for invoice in invoice_records:
        validation = validate_taxi_invoice(invoice, checkin_records, selected_month)
        validated_records.append({
            'invoice': invoice,
            'valid': validation['valid'],
            'reason': validation['reason'],
            'work_hours': validation['work_hours']
        })
    
    valid_count = sum(1 for r in validated_records if r['valid'])
    valid_amount = sum(r['invoice']['amount'] for r in validated_records if r['valid'])
    total_invoice_amount = sum(r['invoice']['amount'] for r in validated_records)
    
    st.info(f"""
    **报销规则说明：**
    - 发票日期必须在费用月份范围内：{expense_month_str}
    - 发票日期必须有对应的打卡记录
    - 该日期工作时长 ≥ {taxi_threshold} 小时
    
    **校验结果：**
    - 发票总数：{len(invoice_records)} 张
    - 符合条件：{valid_count} 张
    - 符合条件金额：¥{valid_amount:.2f}
    - 不符合条件：{len(invoice_records) - valid_count} 张
    """)
    
    if invoice_records:
        st.markdown("#### 数据预览（含校验结果）")
        
        preview_data = []
        for record in validated_records:
            invoice = record['invoice']
            date_str = invoice['date'] if isinstance(invoice['date'], str) else invoice['date'].strftime('%Y-%m-%d')
            
            preview_data.append({
                '日期': date_str,
                '服务商': invoice.get('company', '未知'),
                '起点': invoice.get('start_location', ''),
                '终点': invoice.get('end_location', ''),
                '金额': f"¥{invoice['amount']:.2f}",
                '工作时长': f"{record['work_hours']:.1f}h" if record['work_hours'] > 0 else '-',
                '状态': '✅' if record['valid'] else '❌',
                '原因': record['reason']
            })
        
        df_preview = pd.DataFrame(preview_data)
        st.dataframe(df_preview, use_container_width=True, hide_index=True)
        
        if valid_count == 0:
            st.warning("⚠️ 没有符合条件的发票记录，无法生成报销明细")
        else:
            st.markdown("---")
            
            col_gen, col_down, col_zip = st.columns([1, 1, 1])
            
            with col_gen:
                if st.button("📊 生成报销明细", type="primary", use_container_width=True, key='gen_taxi'):
                    valid_records = [r for r in validated_records if r['valid']]
                    excel_data, record_count, total_amount = generate_taxi_excel(valid_records, selected_month)
                    
                    st.session_state['taxi_excel'] = excel_data
                    st.session_state['taxi_count'] = record_count
                    st.session_state['taxi_amount'] = total_amount
                    st.session_state['taxi_validated_records'] = valid_records
                    
                    st.success(f"生成成功！共 {record_count} 条记录，总金额 ¥{total_amount:.2f}")
            
            with col_down:
                if 'taxi_excel' in st.session_state:
                    output_config = db.get_config('output') or {'default_name': '姓名'}
                    default_name = output_config['default_name']
                    month_num = selected_month[-2:]
                    file_name = f"{default_name}_加班打车报销明细表_{month_num}月.xls"
                    
                    st.download_button(
                        label="📥 下载明细表",
                        data=st.session_state['taxi_excel'],
                        file_name=file_name,
                        mime="application/vnd.ms-excel",
                        use_container_width=True,
                        key='download_taxi'
                    )
            
            with col_zip:
                if 'taxi_excel' in st.session_state:
                    output_config = db.get_config('output') or {'default_name': '姓名'}
                    default_name = output_config['default_name']
                    month_num = selected_month[-2:]
                    file_name = f"{default_name}_加班打车报销明细表_{month_num}月.xls"
                    zip_name = f"{default_name}_打车报销_{month_num}月.zip"
                    
                    if st.button("📦 打包下载(含发票附件)", use_container_width=True, key='zip_taxi'):
                        valid_records = st.session_state.get('taxi_validated_records', [r for r in validated_records if r['valid']])
                        zip_data = create_taxi_zip(
                            st.session_state['taxi_excel'],
                            selected_month,
                            file_name,
                            valid_records
                        )
                        st.session_state['taxi_zip'] = zip_data
                        st.session_state['taxi_zip_name'] = zip_name
                    
                    if 'taxi_zip' in st.session_state:
                        st.download_button(
                            label=f"📥 下载 {st.session_state['taxi_zip_name']}",
                            data=st.session_state['taxi_zip'],
                            file_name=st.session_state['taxi_zip_name'],
                            mime="application/zip",
                            use_container_width=True,
                            key='download_taxi_zip'
                        )
    else:
        st.warning("该月份暂无发票记录")

st.markdown("---")

st.markdown("### 📋 导出历史")

export_history = db.get_export_history(10)

if export_history:
    df_history = pd.DataFrame(export_history)
    df_history['created_at'] = pd.to_datetime(df_history['created_at']).dt.strftime('%Y-%m-%d %H:%M')
    df_history = df_history[['month_folder', 'export_type', 'file_path', 'record_count', 'total_amount', 'created_at']]
    df_history.columns = ['月份', '类型', '文件名', '记录数', '总金额', '导出时间']
    
    st.dataframe(df_history, use_container_width=True, hide_index=True)
else:
    st.info("暂无导出历史记录")
