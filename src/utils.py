import os
import re
import pandas as pd
import pdfplumber
import tempfile
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import database as db

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
UPLOADS_DIR = os.path.join(DATA_DIR, 'uploads')
OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'output')

def parse_checkin_excel(file_path: str) -> Tuple[List[Dict], str]:
    records = []
    error_msg = ""
    
    try:
        sheet_name = "概况统计与打卡明细"
        skip_rows = 3
        
        try:
            df = pd.read_excel(file_path, sheet_name=sheet_name, skiprows=skip_rows)
        except:
            df = pd.read_excel(file_path, skiprows=skip_rows)
        
        possible_columns = ['实际工作时长(小时)', '实际工作时长', '工作时长', 'Actual Work Hours']
        work_hours_column = None
        for col in possible_columns:
            if col in df.columns:
                work_hours_column = col
                break
        
        if work_hours_column is None:
            return [], "未找到工作时长列，请检查Excel文件结构"
        
        date_column = df.columns[0]
        
        for index, row in df.iterrows():
            try:
                work_hours_raw = row.get(work_hours_column)
                if work_hours_raw is None or pd.isna(work_hours_raw) or work_hours_raw in ['--', '', '休息', '正常（休息）']:
                    continue
                
                try:
                    work_hours = float(work_hours_raw)
                except ValueError:
                    continue
                
                date_str = row.get(date_column, '')
                
                if pd.isna(date_str):
                    continue
                
                date = None
                if isinstance(date_str, str) and date_str:
                    clean_date_str = str(date_str).split(' ')[0] if ' ' in str(date_str) else str(date_str)
                    date_formats = ['%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d', '%m/%d/%Y']
                    for fmt in date_formats:
                        try:
                            date = datetime.strptime(clean_date_str, fmt)
                            break
                        except:
                            continue
                elif isinstance(date_str, pd.Timestamp):
                    date = date_str.to_pydatetime()
                
                if date:
                    records.append({
                        'date': date,
                        'work_hours': work_hours
                    })
            except Exception as e:
                continue
        
    except Exception as e:
        error_msg = f"解析Excel文件失败: {str(e)}"
    
    return records, error_msg

def extract_amount_from_text(text: str) -> float:
    amount_patterns = [
        r'(\d+\.?\d{2})元',
        r'金额[:：]\s*(\d+\.?\d{2})',
        r'合计[:：]\s*(\d+\.?\d{2})',
        r'￥(\d+\.?\d{2})',
        r'小写[）\)]\s*[￥¥]?\s*(\d+\.?\d{2})',
    ]
    
    for pattern in amount_patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            try:
                potential_amount = float(match)
                if 5 <= potential_amount <= 1000:
                    return potential_amount
            except:
                continue
    
    return 0.0

def extract_date_from_text(text: str) -> Optional[datetime]:
    date_patterns = [
        r'行程时间[:：]\s*(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})',
        r'上车时间[:：]\s*(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})',
        r'(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})\s*\d{2}:\d{2}',
        r'(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})',
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            groups = match.groups()
            if len(groups) == 3:
                try:
                    year, month, day = map(int, groups)
                    return datetime(year, month, day)
                except:
                    continue
    
    return None

def extract_company_from_text(text: str, file_name: str) -> str:
    company_match = re.search(r'【([^】]*)】', file_name)
    if company_match:
        return company_match.group(1)
    
    return "未知"

def extract_taxi_locations_from_text(text: str) -> Tuple[str, str]:
    lines = text.split('\n')
    
    header_found = False
    start_col_idx = None
    end_col_idx = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        if '序号' in line and '起点' in line and '终点' in line:
            header_found = True
            parts = re.split(r'\s+', line)
            for i, part in enumerate(parts):
                if '起点' in part:
                    start_col_idx = i
                elif '终点' in part:
                    end_col_idx = i
            continue
        
        if header_found and start_col_idx is not None and end_col_idx is not None:
            if re.search(r'^\d+\s', line):
                parts = re.split(r'\s+', line)
                
                time_cols_before_start = 0
                for i in range(1, min(start_col_idx, len(parts))):
                    if re.match(r'\d{2}:\d{2}$', parts[i]):
                        time_cols_before_start += 1
                
                actual_start_idx = start_col_idx + time_cols_before_start
                actual_end_idx = end_col_idx + time_cols_before_start
                
                if len(parts) > max(actual_start_idx, actual_end_idx):
                    start_location = parts[actual_start_idx] if actual_start_idx < len(parts) else ""
                    end_location = parts[actual_end_idx] if actual_end_idx < len(parts) else ""
                    
                    if start_location and end_location:
                        if '元' in start_location:
                            start_location = start_location.replace('元', '')
                        if '元' in end_location:
                            end_location = end_location.replace('元', '')
                        
                        if start_location and end_location and '元' not in start_location:
                            return start_location, end_location
    
    return "", ""

def parse_taxi_pdf(file_path: str) -> Optional[Dict]:
    try:
        with pdfplumber.open(file_path) as pdf:
            full_text = ""
            tables = []
            
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"
                
                page_tables = page.extract_tables()
                if page_tables:
                    tables.extend(page_tables)
            
            full_text = full_text.replace('\r', '').replace('\t', ' ')
            
            amount = extract_amount_from_text(full_text)
            date = extract_date_from_text(full_text)
            company = extract_company_from_text(full_text, os.path.basename(file_path))
            
            start_location, end_location = extract_taxi_locations_from_text(full_text)
            
            if not start_location:
                start_location = "起点未知"
            if not end_location:
                end_location = "终点未知"
            
            return {
                'amount': amount,
                'date': date or datetime.now(),
                'start_location': start_location,
                'end_location': end_location,
                'company': company,
                'source_file': os.path.basename(file_path)
            }
    except Exception as e:
        return None
    
    return None

def generate_month_folder_name(date: Optional[datetime] = None) -> str:
    if date is None:
        date = datetime.now()
    
    year_short = str(date.year)[-2:]
    month = str(date.month).zfill(2)
    
    return f"{year_short}_{month}"

def check_reimburse_eligibility(work_hours: float, reimburse_type: str) -> Tuple[bool, float, str]:
    config = db.get_config('reimburse_rules')
    
    if not config:
        config = {
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
    
    if reimburse_type == 'dinner':
        threshold = config['night_meal']['dinner_threshold']
        amount = config['night_meal']['dinner_amount']
        if work_hours >= threshold:
            return True, amount, f'工作时长{work_hours}小时，超过{threshold}小时阈值'
        return False, 0, f'工作时长{work_hours}小时，未达到{threshold}小时阈值'
    
    elif reimburse_type == 'night':
        threshold = config['night_meal']['night_threshold']
        amount = config['night_meal']['night_amount']
        if work_hours >= threshold:
            return True, amount, f'工作时长{work_hours}小时，超过{threshold}小时阈值'
        return False, 0, f'工作时长{work_hours}小时，未达到{threshold}小时阈值'
    
    elif reimburse_type == 'taxi':
        threshold = config['taxi']['threshold']
        if work_hours > threshold:
            return True, 0, f'工作时长{work_hours}小时，超过{threshold}小时阈值'
        return False, 0, f'工作时长{work_hours}小时，未达到{threshold}小时阈值'
    
    return False, 0, '未知报销类型'

def format_date(date_str: str) -> str:
    try:
        if isinstance(date_str, str):
            dt = datetime.strptime(date_str, '%Y-%m-%d')
            return dt.strftime('%Y年%m月%d日')
    except:
        pass
    return date_str

def get_weekday_name(date_str: str) -> str:
    try:
        if isinstance(date_str, str):
            dt = datetime.strptime(date_str, '%Y-%m-%d')
            weekday_map = {0: '星期一', 1: '星期二', 2: '星期三', 3: '星期四', 4: '星期五', 5: '星期六', 6: '星期日'}
            return weekday_map[dt.weekday()]
    except:
        pass
    return ""

def save_uploaded_file(uploaded_file, target_dir: str) -> str:
    os.makedirs(target_dir, exist_ok=True)
    
    file_path = os.path.join(target_dir, uploaded_file.name)
    
    with open(file_path, 'wb') as f:
        f.write(uploaded_file.getbuffer())
    
    return file_path

def validate_month_folder_name(name: str) -> bool:
    pattern = r'^\d{2}_\d{2}$'
    return bool(re.match(pattern, name))

def find_matching_invoice(itinerary_path: str, invoice_folder: str) -> Optional[str]:
    base_name = os.path.basename(itinerary_path)
    name_without_ext = os.path.splitext(base_name)[0]
    
    if '行程单' in name_without_ext:
        invoice_name = name_without_ext.replace('行程单', '发票')
    else:
        invoice_name = name_without_ext
    
    possible_names = [
        f"{invoice_name}.pdf",
        f"{invoice_name}.PDF",
    ]
    
    for inv_name in possible_names:
        potential_path = os.path.join(invoice_folder, inv_name)
        if os.path.exists(potential_path):
            return potential_path
    
    return None

def find_matching_itinerary(invoice_path: str, invoice_folder: str) -> Optional[str]:
    base_name = os.path.basename(invoice_path)
    name_without_ext = os.path.splitext(base_name)[0]
    
    if '发票' in name_without_ext:
        itinerary_name = name_without_ext.replace('发票', '行程单')
    else:
        itinerary_name = name_without_ext
    
    possible_names = [
        f"{itinerary_name}.pdf",
        f"{itinerary_name}.PDF",
    ]
    
    for itin_name in possible_names:
        potential_path = os.path.join(invoice_folder, itin_name)
        if os.path.exists(potential_path):
            return potential_path
    
    return None
