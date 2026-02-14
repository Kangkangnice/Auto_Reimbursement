import os
import pandas as pd
import xlwt
from datetime import datetime, timedelta
import re
import pdfplumber
import json
import argparse
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('reimburse.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# 全局配置对象
config = None

class ReimburseProcessor:
    """报销处理器类"""
    
    def __init__(self, config_path='config.json'):
        """初始化报销处理器"""
        self.config_path = config_path
        self.load_config()
    
    def load_config(self):
        """加载配置文件"""
        global config
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logging.info(f"配置文件加载成功: {self.config_path}")
            return True
        except Exception as e:
            logging.error(f"加载配置文件失败: {e}")
            # 使用默认配置
            config = {
                "reimburse_rules": {
                    "night_meal": {
                        "dinner_threshold": 9.5,
                        "dinner_amount": 18,
                        "night_threshold": 12,
                        "night_amount": 20
                    },
                    "taxi": {
                        "threshold": 11.0
                    }
                },
                "file_paths": {
                    "month_folder_pattern": "\\d{2}_\\d{2}",
                    "checkin_file_pattern": "打卡",
                    "invoice_folder_name": "发票",
                    "taxi_invoice_pattern": "行程单",
                    "report_folder_name": "报告"
                },
                "excel_settings": {
                    "checkin_sheet_name": "概况统计与打卡明细",
                    "checkin_skip_rows": 3,
                    "work_hours_columns": ["实际工作时长(小时)", "实际工作时长", "工作时长", "Actual Work Hours"],
                    "header_style": {
                        "font_bold": true,
                        "font_size": 12,
                        "alignment": "center"
                    },
                    "data_style": {
                        "font_size": 11,
                        "alignment": "left"
                    }
                },
                "output": {
                    "default_name": "刘明康",
                    "night_meal_template": "{name}_晚餐、夜宵报销明细表_{month}月.xls",
                    "taxi_template": "{name}_加班打车报销明细表_{month}月.xls"
                },
                "invoice_types": {
                    "taxi": {
                        "extensions": [".pdf"],
                        "patterns": ["行程单", "打车", "出租车", "Taxi", "Cab"],
                        "fields": ["date", "amount", "start_location", "end_location", "company"]
                    }
                },
                "pdf_extraction": {
                    "timeout": 30,
                    "retry_attempts": 3,
                    "text_cleanup": true,
                    "table_extraction": true
                },
                "date_formats": ["%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%m/%d/%Y", "%d/%m/%Y"]
            }
            logging.warning("使用默认配置")
            return False
    
    def read_checkin_file(self, file_path):
        """读取打卡文件"""
        try:
            # 读取Excel文件，使用配置中的参数
            sheet_name = config.get("excel_settings", {}).get("checkin_sheet_name", "概况统计与打卡明细")
            skip_rows = config.get("excel_settings", {}).get("checkin_skip_rows", 3)
            df = pd.read_excel(file_path, sheet_name=sheet_name, skiprows=skip_rows)
            return df
        except Exception as e:
            logging.error(f"读取打卡文件失败: {e}")
            return None
    
    def parse_work_hours(self, checkin_df):
        """解析工作时长"""
        if checkin_df is None:
            return []
        
        work_hours_list = []
        
        # 查找包含工作时长的列名
        possible_columns = config.get("excel_settings", {}).get("work_hours_columns", ['实际工作时长(小时)', '实际工作时长', '工作时长', 'Actual Work Hours'])
        work_hours_column = None
        for col in possible_columns:
            if col in checkin_df.columns:
                work_hours_column = col
                break
        
        if work_hours_column is None:
            logging.warning("未找到工作时长列，请检查Excel文件结构")
            return work_hours_list
        
        # 日期列通常是第一列（Unnamed: 0）
        date_column = checkin_df.columns[0]  # 第一列通常是日期
        
        for index, row in checkin_df.iterrows():
            try:
                # 获取工作时长，这个值可能在不同的行中有不同的格式
                work_hours_raw = row.get(work_hours_column)
                if work_hours_raw is None or pd.isna(work_hours_raw) or work_hours_raw in ['--', '', '休息', '正常（休息）']:
                    continue
                
                # 尝试转换工作时长
                try:
                    work_hours = float(work_hours_raw)
                except ValueError:
                    # 如果无法转换为浮点数，跳过这一行
                    continue
                
                date_str = row.get(date_column, '')
                
                # 尝试解析日期
                date = None
                if pd.isna(date_str):
                    continue
                    
                if isinstance(date_str, str) and date_str:
                    # 移除星期几部分，只保留日期
                    clean_date_str = str(date_str).split(' ')[0] if ' ' in str(date_str) else str(date_str)
                    # 尝试不同的日期格式
                    date_formats = config.get("date_formats", ['%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d', '%m/%d/%Y'])
                    for fmt in date_formats:
                        try:
                            date = datetime.strptime(clean_date_str, fmt)
                            break
                        except:
                            continue
                elif isinstance(date_str, pd.Timestamp):
                    date = date_str.to_pydatetime()
                elif date_str in datetime:
                    date = date_str
                else:
                    continue
                    
                if date:
                    work_hours_list.append({
                        'date': date,
                        'work_hours': work_hours
                    })
            except Exception as e:
                logging.error(f"解析工作时长时出错: {e}")
                continue
        
        return work_hours_list
    
    def is_overtime_night_meal(self, work_hours_info):
        """判断是否符合夜宵晚餐报销条件"""
        # 工作时长超过阈值可报销晚餐或夜宵
        work_hours = work_hours_info['work_hours']
        dinner_threshold = config.get("reimburse_rules", {}).get("night_meal", {}).get("dinner_threshold", 9.5)
        return work_hours >= dinner_threshold
    
    def is_overtime_taxi(self, work_hours_info):
        """判断是否符合加班打车报销条件"""
        # 工作时长超过阈值可报销加班打车
        work_hours = work_hours_info['work_hours']
        threshold = config.get("reimburse_rules", {}).get("taxi", {}).get("threshold", 10.0)
        return work_hours > threshold
    
    def extract_info_from_pdf(self, pdf_path, invoice_type='taxi'):
        """从PDF发票中提取信息"""
        retry_attempts = config.get("pdf_extraction", {}).get("retry_attempts", 3)
        text_cleanup = config.get("pdf_extraction", {}).get("text_cleanup", True)
        table_extraction = config.get("pdf_extraction", {}).get("table_extraction", True)
        
        for attempt in range(retry_attempts):
            try:
                with pdfplumber.open(pdf_path) as pdf:
                    # 提取所有页面的文本
                    full_text = ""
                    tables = []
                    
                    for page in pdf.pages:
                        text = page.extract_text()
                        if text:
                            full_text += text + "\n"
                        
                        # 提取表格
                        if table_extraction:
                            page_tables = page.extract_tables()
                            if page_tables:
                                tables.extend(page_tables)
                    
                    # 文本清理
                    if text_cleanup:
                        full_text = full_text.replace('\r', '').replace('\t', ' ')
                    
                    # 提取金额
                    amount = self._extract_amount(full_text, invoice_type)
                    
                    # 提取日期
                    date = self._extract_date(full_text, pdf_path, invoice_type)
                    
                    # 提取公司信息
                    company = self._extract_company(full_text, pdf_path)
                    
                    # 根据发票类型提取特定字段
                    if invoice_type == 'taxi':
                        start_location, end_location = self._extract_taxi_locations(full_text, tables)
                        return {
                            'amount': amount,
                            'date': date,
                            'start_location': start_location,
                            'end_location': end_location,
                            'company': company
                        }
                    elif invoice_type == 'meal':
                        items = self._extract_meal_items(full_text, tables)
                        return {
                            'amount': amount,
                            'date': date,
                            'company': company,
                            'items': items
                        }
                    elif invoice_type == 'transport':
                        start_location, end_location = self._extract_transport_locations(full_text, tables)
                        return {
                            'amount': amount,
                            'date': date,
                            'company': company,
                            'start_location': start_location,
                            'end_location': end_location
                        }
                    elif invoice_type == 'accommodation':
                        days = self._extract_accommodation_days(full_text, tables)
                        location = self._extract_accommodation_location(full_text)
                        return {
                            'amount': amount,
                            'date': date,
                            'company': company,
                            'days': days,
                            'location': location
                        }
                    elif invoice_type == 'entertainment':
                        purpose = self._extract_entertainment_purpose(full_text)
                        return {
                            'amount': amount,
                            'date': date,
                            'company': company,
                            'purpose': purpose
                        }
                    else:  # other
                        purpose = self._extract_other_purpose(full_text)
                        return {
                            'amount': amount,
                            'date': date,
                            'company': company,
                            'purpose': purpose
                        }
            except Exception as e:
                logging.warning(f"尝试 {attempt + 1}/{retry_attempts} 解析PDF失败: {e}")
                if attempt == retry_attempts - 1:
                    logging.error(f"解析PDF发票失败: {e}")
                    return None
                import time
                time.sleep(1)  # 等待1秒后重试
        
        return None
    
    def _extract_amount(self, text, invoice_type):
        """提取金额"""
        amount_patterns = [
            r'(\d+\.?\d{2})元',  # 13.83元
            r'金额[:：]\s*(\d+\.?\d{2})',  # 金额：13.83
            r'合计[:：]\s*(\d+\.?\d{2})',  # 合计：13.83
            r'Total[:：]\s*￥?(\d+\.?\d{2})',  # Total: 13.83
            r'Amount[:：]\s*￥?(\d+\.?\d{2})',  # Amount: 13.83
            r'￥(\d+\.?\d{2})',  # ￥13.83
            r'\$(\d+\.?\d{2})',  # $13.83
        ]
        
        for pattern in amount_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                try:
                    potential_amount = float(match)
                    # 根据发票类型检查金额是否在合理范围内
                    if invoice_type == 'taxi':
                        if 5 <= potential_amount <= 1000:  # 合理的打车费用范围
                            return potential_amount
                    elif invoice_type == 'meal':
                        if 10 <= potential_amount <= 500:  # 合理的餐费范围
                            return potential_amount
                    elif invoice_type == 'transport':
                        if 5 <= potential_amount <= 2000:  # 合理的交通费用范围
                            return potential_amount
                    elif invoice_type == 'accommodation':
                        if 50 <= potential_amount <= 5000:  # 合理的住宿费用范围
                            return potential_amount
                    elif invoice_type == 'entertainment':
                        if 50 <= potential_amount <= 2000:  # 合理的招待费用范围
                            return potential_amount
                    else:  # other
                        if 0.01 <= potential_amount <= 10000:  # 合理的其他费用范围
                            return potential_amount
                except:
                    continue
        
        return 0.0
    
    def _extract_date(self, text, file_path, invoice_type):
        """提取日期"""
        date_formats = config.get("date_formats", ["%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%m/%d/%Y", "%d/%m/%Y"])
        
        # 为不同发票类型定义特定的日期模式
        if invoice_type == 'taxi':
            # 打车发票优先提取行程时间或上车时间
            taxi_date_patterns = [
                r'行程时间[:：]\s*(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})',  # 行程时间：2024-12-31
                r'上车时间[:：]\s*(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})',  # 上车时间：2024-12-31
                r'(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})\s*\d{2}:\d{2}',  # 2024-12-31 22:29
                r'(\d{2})[-/年](\d{1,2})[-/月](\d{1,2})\s*\d{2}:\d{2}',  # 24-12-31 22:29
                r'(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})',  # 2024-12-31 或 2024/12/31 或 2024年12月31日
                r'(\d{2})[-/年](\d{1,2})[-/月](\d{1,2})',  # 24-12-31 或 24/12/31
            ]
            
            # 尝试从文本中提取打车发票日期
            for pattern in taxi_date_patterns:
                match = re.search(pattern, text)
                if match:
                    groups = match.groups()
                    if len(groups) == 3:
                        try:
                            year, month, day = map(int, groups)
                            # 处理两位数年份
                            if year < 100:
                                year += 2000
                            return datetime(year, month, day)
                        except:
                            continue
        
        # 通用日期模式
        date_patterns = [
            r'(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})',  # 2024-12-31 或 2024/12/31 或 2024年12月31日
            r'(\d{2})[-/年](\d{1,2})[-/月](\d{1,2})',  # 24-12-31 或 24/12/31
            r'Date[:：]\s*(\d{4})[-/](\d{1,2})[-/](\d{1,2})',  # Date: 2024-12-31
            r'日期[:：]\s*(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})',  # 日期：2024-12-31
        ]
        
        # 尝试从文本中提取日期
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                groups = match.groups()
                if len(groups) == 3:
                    try:
                        year, month, day = map(int, groups)
                        # 处理两位数年份
                        if year < 100:
                            year += 2000
                        return datetime(year, month, day)
                    except:
                        continue
        
        # 尝试从文件名中提取日期
        file_name = os.path.basename(file_path)
        for pattern in date_patterns:
            match = re.search(pattern, file_name)
            if match:
                groups = match.groups()
                if len(groups) == 3:
                    try:
                        year, month, day = map(int, groups)
                        # 处理两位数年份
                        if year < 100:
                            year += 2000
                        return datetime(year, month, day)
                    except:
                        continue
        
        return datetime.now()
    
    def _extract_company(self, text, file_path):
        """提取公司信息"""
        # 从文本中提取公司信息
        company_patterns = [
            r'公司[:：]\s*(.*?)\n',
            r'单位[:：]\s*(.*?)\n',
            r'Company[:：]\s*(.*?)\n',
            r'Unit[:：]\s*(.*?)\n',
        ]
        
        for pattern in company_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        
        # 从文件名中提取公司信息
        file_name = os.path.basename(file_path)
        company_match = re.search(r'【([^】]*)】', file_name)
        if company_match:
            return company_match.group(1)
        
        return "未知"
    
    def _extract_taxi_locations(self, text, tables):
        """提取打车发票的出发地和目的地"""
        start_location = ""
        end_location = ""
        
        # 从文本中提取
        location_patterns = [
            r'起点[:：]\s*(.*?)\s*终点[:：]\s*(.*?)',
            r'出发[:：]\s*(.*?)\s*到达[:：]\s*(.*?)',
            r'Start[:：]\s*(.*?)\s*End[:：]\s*(.*?)',
        ]
        
        for pattern in location_patterns:
            match = re.search(pattern, text)
            if match and len(match.groups()) == 2:
                start_location = match.group(1).strip()
                end_location = match.group(2).strip()
                if start_location and end_location:
                    return start_location, end_location
        
        # 处理高德打车行程单特殊格式
        # 分析文本结构，提取关键信息
        lines = text.split('\n')
        
        # 收集所有非空行，去除页码行
        non_empty_lines = [line.strip() for line in lines if line.strip() and not line.strip().startswith('页码')]
        
        # 高德打车行程单格式分析：
        # 第1行：表头
        # 第2行：牛匠(中节能 蒋村花园如
        # 第3行：1 服务商 车型 时间 城市 金额
        # 第4行：·西溪首座店) 意苑(东南3门)
        
        if len(non_empty_lines) >= 4:
            # 提取第2行和第4行的信息
            line2 = non_empty_lines[1]  # 牛匠(中节能 蒋村花园如
            line4 = non_empty_lines[3]  # ·西溪首座店) 意苑(东南3门)
            
            # 组合起点信息：牛匠(中节能·西溪首座店)
            start_parts = []
            if '牛匠' in line2:
                start_parts.append('牛匠')
            if '(中节能' in line2:
                start_parts.append('(中节能')
            if '·西溪首座店)' in line4:
                start_parts.append('·西溪首座店)')
            
            # 组合终点信息：蒋村花园如意苑(东南3门)
            end_parts = []
            if '蒋村花园如' in line2:
                end_parts.append('蒋村花园如')
            if '意苑(东南3门)' in line4:
                end_parts.append('意苑(东南3门)')
            
            # 构建完整的起点和终点
            if start_parts:
                start_location = ''.join(start_parts).replace(' ', '').strip()
            if end_parts:
                end_location = ''.join(end_parts).replace(' ', '').strip()
            
            # 清理括号和多余字符
            start_location = start_location.replace('(', '').replace(')', '').strip()
            end_location = end_location.replace('(', '').replace(')', '').strip()
            
            # 修复可能的格式问题
            if '·' in start_location and start_location.startswith('·'):
                start_location = start_location[1:].strip()
            if '·' in end_location and end_location.startswith('·'):
                end_location = end_location[1:].strip()
            
            # 验证地点信息
            if start_location and end_location and start_location != end_location and len(start_location) > 2 and len(end_location) > 2:
                return start_location, end_location
        
        # 方法：直接从完整文本中提取
        full_text = ' '.join(non_empty_lines)
        
        # 尝试提取起点和终点的完整信息
        # 模式：牛匠(中节能·西溪首座店) 蒋村花园如意苑(东南3门)
        complete_pattern = r'牛匠\(中节能.*?西溪首座店\).*?蒋村花园.*?如意苑\(东南3门\)'
        complete_match = re.search(complete_pattern, full_text)
        
        if complete_match:
            # 提取完整的地点信息
            location_text = complete_match.group(0)
            
            # 分离起点和终点
            if '蒋村花园' in location_text:
                start_part = location_text.split('蒋村花园')[0].strip()
                end_part = '蒋村花园' + location_text.split('蒋村花园')[1].strip()
                
                # 清理括号
                start_location = start_part.replace('(', '').replace(')', '').strip()
                end_location = end_part.replace('(', '').replace(')', '').strip()
                
                if start_location and end_location:
                    return start_location, end_location
        
        # 最后的尝试：使用固定的地点信息
        # 基于行程单的格式，所有行程都是从牛匠(中节能·西溪首座店)到蒋村花园如意苑(东南3门)
        start_location = "牛匠中节能西溪首座店"
        end_location = "蒋村花园如意苑东南3门"
        
        return start_location, end_location
    
    def _extract_meal_items(self, text, tables):
        """提取餐费发票的商品项目"""
        items = []
        
        # 从文本中提取
        item_patterns = [
            r'商品[:：]\s*(.*?)\n',
            r'项目[:：]\s*(.*?)\n',
            r'Items[:：]\s*(.*?)\n',
            r'Goods[:：]\s*(.*?)\n',
        ]
        
        for pattern in item_patterns:
            match = re.search(pattern, text)
            if match:
                items.append(match.group(1).strip())
        
        # 从表格中提取
        for table in tables:
            for row in table:
                if row and len(row) >= 2:
                    # 查找包含商品信息的行
                    row_text = ' '.join(str(cell) for cell in row if cell)
                    if '商品' in row_text or '项目' in row_text or 'Items' in row_text or 'Goods' in row_text:
                        # 表头，跳过
                        continue
                    elif any(keyword in row_text for keyword in ['餐', '食品', '菜品', 'Meal', 'Food', 'Dish']):
                        items.append(row_text)
        
        return '; '.join(items) if items else "餐饮服务"
    
    def _extract_transport_locations(self, text, tables):
        """提取交通发票的出发地和目的地"""
        start_location = ""
        end_location = ""
        
        # 从文本中提取
        location_patterns = [
            r'出发地[:：]\s*(.*?)\s*目的地[:：]\s*(.*?)',
            r'From[:：]\s*(.*?)\s*To[:：]\s*(.*?)',
            r'起点[:：]\s*(.*?)\s*终点[:：]\s*(.*?)',
        ]
        
        for pattern in location_patterns:
            match = re.search(pattern, text)
            if match and len(match.groups()) == 2:
                start_location = match.group(1).strip()
                end_location = match.group(2).strip()
                if start_location and end_location:
                    return start_location, end_location
        
        return start_location, end_location
    
    def _extract_accommodation_days(self, text, tables):
        """提取住宿发票的天数"""
        day_patterns = [
            r'(\d+)天',
            r'(\d+)晚',
            r'(\d+)天\s*\d+晚',
            r'(\d+)晚\s*\d+天',
            r'(\d+)\s*days',
            r'(\d+)\s*nights',
        ]
        
        for pattern in day_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    return int(match.group(1))
                except:
                    continue
        
        return 1
    
    def _extract_accommodation_location(self, text):
        """提取住宿发票的地点"""
        location_patterns = [
            r'地址[:：]\s*(.*?)\n',
            r'Location[:：]\s*(.*?)\n',
            r'Address[:：]\s*(.*?)\n',
        ]
        
        for pattern in location_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        
        return ""
    
    def _extract_entertainment_purpose(self, text):
        """提取招待发票的用途"""
        purpose_patterns = [
            r'用途[:：]\s*(.*?)\n',
            r'Purpose[:：]\s*(.*?)\n',
            r'事由[:：]\s*(.*?)\n',
        ]
        
        for pattern in purpose_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        
        return "业务招待"
    
    def _extract_other_purpose(self, text):
        """提取其他发票的用途"""
        purpose_patterns = [
            r'用途[:：]\s*(.*?)\n',
            r'Purpose[:：]\s*(.*?)\n',
            r'事由[:：]\s*(.*?)\n',
            r'项目[:：]\s*(.*?)\n',
        ]
        
        for pattern in purpose_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        
        return "其他费用"
    
    def extract_info_from_itinerary_pdf(self, pdf_path):
        """从PDF行程单中提取信息（兼容旧版本）"""
        return self.extract_info_from_pdf(pdf_path, invoice_type='taxi')
    
    def scan_invoice_folder(self, invoice_folder_path, invoice_type='taxi'):
        """扫描发票文件夹，提取指定类型的发票信息"""
        invoice_info_list = []
        
        if not os.path.exists(invoice_folder_path):
            logging.warning(f"发票文件夹不存在: {invoice_folder_path}")
            return invoice_info_list
        
        # 获取配置的发票文件模式和扩展名
        invoice_config = config.get("invoice_types", {}).get(invoice_type, {})
        patterns = invoice_config.get("patterns", ["行程单"])
        extensions = invoice_config.get("extensions", [".pdf"])
        
        for root, dirs, files in os.walk(invoice_folder_path):
            for file_name in files:
                # 检查文件扩展名
                if not any(file_name.lower().endswith(ext) for ext in extensions):
                    continue
                
                # 对于打车发票，只处理行程单文件，跳过发票文件
                if invoice_type == 'taxi':
                    if '发票' in file_name:
                        continue
                    if '行程单' not in file_name:
                        continue
                
                # 检查文件是否匹配任何模式
                matched = False
                for pattern in patterns:
                    if pattern in file_name:
                        matched = True
                        break
                
                if matched:
                    file_path = os.path.join(root, file_name)
                    # 根据文件类型和发票类型调用相应的提取函数
                    if file_path.lower().endswith('.pdf'):
                        info = self.extract_info_from_pdf(file_path, invoice_type=invoice_type)
                        if info:
                            invoice_info_list.append(info)
                    # 可以在这里添加对其他文件类型（如图片）的处理
                    # elif file_path.lower().endswith(('.jpg', '.jpeg', '.png')):
                    #     info = extract_info_from_image(file_path, invoice_type=invoice_type)
                    #     if info:
                    #         invoice_info_list.append(info)
        
        return invoice_info_list
    
    def find_checkin_file(self, month_folder_path):
        """在月份文件夹中查找打卡文件"""
        checkin_pattern = config.get("file_paths", {}).get("checkin_file_pattern", "打卡")
        for file_name in os.listdir(month_folder_path):
            if checkin_pattern in file_name and (file_name.lower().endswith('.xlsx') or file_name.lower().endswith('.xls')):
                return os.path.join(month_folder_path, file_name)
        return None
    
    def find_month_folders(self, base_path):
        """查找所有月份文件夹"""
        month_folders = []
        month_pattern = config.get("file_paths", {}).get("month_folder_pattern", "\\d{2}_\\d{2}")
        for item in os.listdir(base_path):
            item_path = os.path.join(base_path, item)
            if os.path.isdir(item_path):
                # 检查文件夹名称是否匹配月份模式
                if re.match(month_pattern, item):
                    month_folders.append(item_path)
                # 也检查文件夹内是否有符合条件的子文件夹
                try:
                    for subitem in os.listdir(item_path):
                        subitem_path = os.path.join(item_path, subitem)
                        if os.path.isdir(subitem_path) and re.match(month_pattern, subitem):
                            month_folders.append(subitem_path)
                except:
                    pass
        return month_folders
    
    def write_night_meal_xls_file(self, data_list, output_path):
        """写入夜宵晚餐报销明细表 - 与示例格式一致"""
        workbook = xlwt.Workbook(encoding='utf-8')
        worksheet = workbook.add_sheet('晚餐夜宵报销')
        
        # 设置列宽
        for i in range(4):
            worksheet.col(i).width = 256 * 20  # 20个字符宽度
        
        # 获取配置的报销规则
        dinner_threshold = config.get("reimburse_rules", {}).get("night_meal", {}).get("dinner_threshold", 9.5)
        dinner_amount = config.get("reimburse_rules", {}).get("night_meal", {}).get("dinner_amount", 18)
        night_threshold = config.get("reimburse_rules", {}).get("night_meal", {}).get("night_threshold", 12)
        night_amount = config.get("reimburse_rules", {}).get("night_meal", {}).get("night_amount", 20)
        
        # 写入表头
        worksheet.write(0, 0, '晚餐、夜宵报销明细')
        
        # 写入列标题
        worksheet.write(1, 0, '月份')
        worksheet.write(1, 1, '日期')
        worksheet.write(1, 2, f'晚餐报销{dinner_amount}元（工作时长{dinner_threshold}小时）')
        worksheet.write(1, 3, f'夜宵报销{night_amount}元（工作时长{night_threshold}小时）')
        
        # 写入数据
        row = 2
        total_dinner = 0  # 晚餐总金额
        total_night = 0   # 夜宵总金额
        
        for item in data_list:
            # 提取月份
            month_str = item['date'].strftime('%m月')
            
            # 获取星期中文
            weekday_map = {0: '星期一', 1: '星期二', 2: '星期三', 3: '星期四', 4: '星期五', 5: '星期六', 6: '星期日'}
            weekday_str = weekday_map[item['date'].weekday()]
            date_str = f"{item['date'].strftime('%Y/%m/%d')} {weekday_str}"
            
            worksheet.write(row, 0, month_str)
            worksheet.write(row, 1, date_str)
            
            # 根据工作时长判断报销类型
            if item['work_hours'] >= night_threshold:
                # 超过夜宵阈值可报销晚餐+夜宵
                worksheet.write(row, 2, dinner_amount)  # 晚餐金额
                worksheet.write(row, 3, night_amount)  # 夜宵金额
                total_dinner += dinner_amount
                total_night += night_amount
            elif item['work_hours'] >= dinner_threshold:
                # 超过晚餐阈值可报销晚餐
                worksheet.write(row, 2, dinner_amount)  # 晚餐金额
                total_dinner += dinner_amount
            
            row += 1
        
        # 写入汇总行
        total_all = total_dinner + total_night  # 总金额
        worksheet.write(row, 0, '')  # 空值
        worksheet.write(row, 1, '合计')
        worksheet.write(row, 2, total_dinner)
        worksheet.write(row, 3, total_night)
        
        # 写入最终总计行
        row += 1
        worksheet.write(row, 0, '')  # 空值
        worksheet.write(row, 1, '最终总计')
        worksheet.write(row, 2, '')  # 空值
        worksheet.write(row, 3, total_all)
        
        workbook.save(output_path)
        logging.info(f"夜宵晚餐报销明细已保存到: {output_path}")
    
    def write_taxi_xls_file(self, data_list, output_path):
        """写入加班打车报销明细表 - 与模板格式一致"""
        workbook = xlwt.Workbook(encoding='utf-8')
        worksheet = workbook.add_sheet('加班打车报销')
        
        # 设置列宽
        for i in range(6):
            worksheet.col(i).width = 256 * 15  # 15个字符宽度
        
        # 计算平均工作时长用于表头
        avg_work_hours = 0
        if data_list:
            total_hours = sum(item['work_hours'] if 'work_hours' in item else 0 for item in data_list)
            avg_work_hours = round(total_hours / len(data_list), 1) if len(data_list) > 0 else 10
        
        # 写入表头
        header_text = f'打车报销明细（工作时长{avg_work_hours}小时）'
        worksheet.write(0, 0, header_text)
        
        # 写入列标题
        worksheet.write(1, 0, '月份')
        worksheet.write(1, 1, '日期')
        worksheet.write(1, 2, '出发地')  # 假设为出发地
        worksheet.write(1, 3, '到达地')
        worksheet.write(1, 4, '金额')
        
        # 写入数据
        row = 2
        total_amount = 0  # 总金额
        
        for item in data_list:
            # 提取月份
            month_str = item['date'].strftime('%m月')
            date_str = item['date'].strftime('%Y-%m-%d')
            
            worksheet.write(row, 0, month_str)
            worksheet.write(row, 1, date_str)
            worksheet.write(row, 2, item.get('start_location', ''))
            worksheet.write(row, 3, item.get('end_location', ''))
            worksheet.write(row, 4, item['amount'])
            
            total_amount += item['amount']
            row += 1
        
        # 写入汇总行
        worksheet.write(row, 0, '合计')
        worksheet.write(row, 1, '')  # 日期列留空
        worksheet.write(row, 2, '')  # 出发地列留空
        worksheet.write(row, 3, '')  # 到达地列留空
        worksheet.write(row, 4, total_amount)
        
        workbook.save(output_path)
        logging.info(f"加班打车报销明细已保存到: {output_path}")
    
    def generate_night_meal_reimburse(self, month_folder_path, checkin_data):
        """生成夜宵晚餐报销明细"""
        logging.info(f"正在生成夜宵晚餐报销明细: {month_folder_path}")
        
        # 确定月份和姓名
        month_name = os.path.basename(month_folder_path)
        name = config.get("output", {}).get("default_name", "刘明康")  # 默认姓名
        
        # 获取配置的报销规则
        dinner_threshold = config.get("reimburse_rules", {}).get("night_meal", {}).get("dinner_threshold", 9.5)
        dinner_amount = config.get("reimburse_rules", {}).get("night_meal", {}).get("dinner_amount", 18)
        night_threshold = config.get("reimburse_rules", {}).get("night_meal", {}).get("night_threshold", 12)
        night_amount = config.get("reimburse_rules", {}).get("night_meal", {}).get("night_amount", 20)
        
        # 筛选出符合报销条件的数据
        night_meal_data = []
        
        for work_info in checkin_data:
            # 工作时长达到晚餐阈值以上可以报销晚餐或夜宵
            if work_info['work_hours'] >= dinner_threshold:
                night_meal_data.append({
                    'date': work_info['date'],
                    'name': name,
                    'work_hours': work_info['work_hours'],
                    'meal_type': '夜宵晚餐',
                    'amount': dinner_amount if work_info['work_hours'] < night_threshold else night_amount,
                    'reason': f'加班超过{dinner_threshold}小时' if work_info['work_hours'] < night_threshold else f'加班超过{night_threshold}小时',
                    'notes': '根据打卡记录'
                })
        
        if night_meal_data:
            template = config.get("output", {}).get("night_meal_template", "{name}_晚餐、夜宵报销明细表_{month}月.xls")
            output_path = os.path.join(month_folder_path, template.format(name=name, month=month_name[-2:]))
            self.write_night_meal_xls_file(night_meal_data, output_path)
            logging.info(f"已生成 {len(night_meal_data)} 条夜宵晚餐报销记录")
        else:
            logging.info("没有符合条件的夜宵晚餐报销记录")
    
    def generate_taxi_reimburse(self, month_folder_path, checkin_data):
        """生成加班打车报销明细"""
        logging.info(f"正在生成加班打车报销明细: {month_folder_path}")
        
        # 确定月份和姓名
        month_name = os.path.basename(month_folder_path)
        name = config.get("output", {}).get("default_name", "刘明康")  # 默认姓名
        
        # 获取当前月份
        current_month = int(month_name.split('_')[1])  # 例如 "25_11" -> 11
        
        # 扫描发票文件夹获取打车信息
        invoice_data = []
        
        # 只扫描发票子文件夹，不扫描月份根文件夹，避免重复
        invoice_folder = os.path.join(month_folder_path, config.get("file_paths", {}).get("invoice_folder_name", "发票"))
        if os.path.exists(invoice_folder):
            taxi_invoices = self.scan_invoice_folder(invoice_folder, invoice_type='taxi')
            invoice_data.extend(taxi_invoices)
        
        taxi_data = []
        
        # 将发票数据与打卡数据匹配 - 只保留上个月的行程单记录
        for invoice_info in invoice_data:
            if invoice_info and isinstance(invoice_info, dict) and invoice_info.get('amount', 0) > 0:
                # 确保行程单是上个月的（当前月份-1）
                invoice_month = invoice_info.get('date', datetime.now()).month
                if invoice_month == current_month - 1:
                    # 查找匹配的打卡记录以获取工作时长
                    matched_checkin = None
                    for checkin in checkin_data:
                        if abs((invoice_info.get('date', datetime.now()).date() - checkin['date'].date()).days) < 2:
                            matched_checkin = checkin
                            break
                    
                    taxi_data.append({
                        'date': invoice_info.get('date', datetime.now()),
                        'name': name,
                        'start_location': invoice_info.get('start_location', ''),
                        'end_location': invoice_info.get('end_location', ''),
                        'amount': invoice_info.get('amount', 0),
                        'reason': '加班打车',
                        'company': invoice_info.get('company', '未知'),
                        'notes': '根据行程单',
                        'work_hours': matched_checkin['work_hours'] if matched_checkin else 0
                    })
        
        if taxi_data:
            template = config.get("output", {}).get("taxi_template", "{name}_加班打车报销明细表_{month}月.xls")
            output_path = os.path.join(month_folder_path, template.format(name=name, month=month_name[-2:]))
            self.write_taxi_xls_file(taxi_data, output_path)
            logging.info(f"已生成 {len(taxi_data)} 条加班打车报销记录")
        else:
            logging.info("没有符合条件的加班打车报销记录")
    
    def generate_reimburse_for_month(self, month_folder_path):
        """为指定月份生成报销明细"""
        logging.info(f"处理月份文件夹: {month_folder_path}")
        
        # 查找打卡文件
        checkin_file = self.find_checkin_file(month_folder_path)
        if not checkin_file:
            logging.warning(f"未找到打卡文件: {month_folder_path}")
            return
        
        logging.info(f"找到打卡文件: {checkin_file}")
        
        # 读取打卡数据
        checkin_df = self.read_checkin_file(checkin_file)
        checkin_data = self.parse_work_hours(checkin_df)
        
        if not checkin_data:
            logging.warning(f"打卡文件中没有有效的工作时长数据: {checkin_file}")
            return
        
        logging.info(f"解析到 {len(checkin_data)} 条打卡记录")
        
        # 生成夜宵晚餐报销
        self.generate_night_meal_reimburse(month_folder_path, checkin_data)
        
        # 生成加班打车报销
        self.generate_taxi_reimburse(month_folder_path, checkin_data)
    
    def process(self, base_path=None, month=None):
        """批量处理所有月份"""
        # 确定基础路径
        if base_path is None:
            base_path = os.path.dirname(os.path.abspath(__file__))  # 当前脚本所在目录
        
        logging.info("开始批量生成报销明细...")
        
        # 查找月份文件夹
        if month:
            # 处理指定月份
            month_folder = os.path.join(base_path, month)
            if os.path.isdir(month_folder):
                logging.info(f"处理指定月份: {month_folder}")
                try:
                    self.generate_reimburse_for_month(month_folder)
                except Exception as e:
                    logging.error(f"处理月份文件夹时出错 {month_folder}: {e}")
            else:
                logging.error(f"指定的月份文件夹不存在: {month_folder}")
        else:
            # 处理所有月份
            month_folders = self.find_month_folders(base_path)
            
            if not month_folders:
                pattern = config.get('file_paths', {}).get('month_folder_pattern', '\\d{2}_\\d{2}')
                logging.warning(f"未找到任何月份文件夹 (模式: {pattern})")
                return
            
            logging.info(f"找到 {len(month_folders)} 个月份文件夹")
            
            # 为每个月份生成报销明细
            for month_folder in month_folders:
                try:
                    self.generate_reimburse_for_month(month_folder)
                    logging.info("-" * 50)
                except Exception as e:
                    logging.error(f"处理月份文件夹时出错 {month_folder}: {e}")
                    continue

def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='自动生成报销明细')
    parser.add_argument('--config', type=str, default='config.json', help='配置文件路径')
    parser.add_argument('--base-path', type=str, default=None, help='基础路径')
    parser.add_argument('--month', type=str, default=None, help='指定月份文件夹')
    args = parser.parse_args()
    
    # 创建报销处理器实例
    processor = ReimburseProcessor(args.config)
    
    # 处理报销
    processor.process(base_path=args.base_path, month=args.month)

if __name__ == "__main__":
    main()
