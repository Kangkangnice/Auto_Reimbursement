import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Optional, Any

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
DB_DIR = os.path.join(DATA_DIR, 'db')
CONFIG_DIR = os.path.join(DATA_DIR, 'config')
UPLOADS_DIR = os.path.join(DATA_DIR, 'uploads')
OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'output')

for dir_path in [DB_DIR, CONFIG_DIR, UPLOADS_DIR, OUTPUT_DIR]:
    os.makedirs(dir_path, exist_ok=True)

DB_PATH = os.path.join(DB_DIR, 'reimburse.db')
CONFIG_PATH = os.path.join(CONFIG_DIR, 'config.json')

def get_connection():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS checkin_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE NOT NULL,
            work_hours REAL NOT NULL,
            month_folder TEXT,
            source_file TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(date, month_folder)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS invoice_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_type TEXT DEFAULT 'taxi',
            date DATE NOT NULL,
            amount REAL NOT NULL,
            start_location TEXT,
            end_location TEXT,
            company TEXT,
            source_file TEXT,
            invoice_file TEXT,
            month_folder TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    try:
        cursor.execute('ALTER TABLE invoice_records ADD COLUMN invoice_file TEXT')
    except:
        pass
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reimburse_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month_folder TEXT NOT NULL,
            reimburse_type TEXT NOT NULL,
            date DATE NOT NULL,
            amount REAL NOT NULL,
            work_hours REAL,
            start_location TEXT,
            end_location TEXT,
            company TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS export_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month_folder TEXT NOT NULL,
            export_type TEXT NOT NULL,
            file_path TEXT NOT NULL,
            record_count INTEGER,
            total_amount REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    init_default_config(cursor)
    
    conn.commit()
    conn.close()

def init_default_config(cursor):
    default_config = {
        'reimburse_rules': json.dumps({
            'night_meal': {
                'dinner_threshold': 9.5,
                'dinner_amount': 18,
                'night_threshold': 12,
                'night_amount': 20
            },
            'taxi': {
                'threshold': 11.0
            }
        }),
        'output': json.dumps({
            'default_name': '姓名',
            'night_meal_template': '{name}_晚餐、夜宵报销明细表_{month}月.xls',
            'taxi_template': '{name}_加班打车报销明细表_{month}月.xls'
        }),
        'file_paths': json.dumps({
            'month_folder_pattern': '\\d{2}_\\d{2}',
            'checkin_file_pattern': '打卡',
            'invoice_folder_name': '发票'
        })
    }
    
    for key, value in default_config.items():
        cursor.execute(
            'INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)',
            (key, value)
        )

def get_config(key: str) -> Optional[Any]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT value FROM config WHERE key = ?', (key,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        try:
            return json.loads(result[0])
        except:
            return result[0]
    return None

def set_config(key: str, value: Any):
    conn = get_connection()
    cursor = conn.cursor()
    
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    
    cursor.execute(
        'INSERT OR REPLACE INTO config (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)',
        (key, value)
    )
    
    conn.commit()
    conn.close()

def get_all_config() -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT key, value FROM config')
    results = cursor.fetchall()
    conn.close()
    
    config = {}
    for key, value in results:
        try:
            config[key] = json.loads(value)
        except:
            config[key] = value
    
    return config

def save_checkin_records(records: List[Dict], month_folder: str, source_file: str):
    conn = get_connection()
    cursor = conn.cursor()
    
    for record in records:
        cursor.execute('''
            INSERT OR REPLACE INTO checkin_records 
            (date, work_hours, month_folder, source_file)
            VALUES (?, ?, ?, ?)
        ''', (
            record['date'].strftime('%Y-%m-%d') if isinstance(record['date'], datetime) else record['date'],
            record['work_hours'],
            month_folder,
            source_file
        ))
    
    conn.commit()
    conn.close()

def get_checkin_records(month_folder: Optional[str] = None) -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    
    if month_folder:
        cursor.execute('''
            SELECT id, date, work_hours, month_folder, source_file, created_at
            FROM checkin_records
            WHERE month_folder = ?
            ORDER BY date
        ''', (month_folder,))
    else:
        cursor.execute('''
            SELECT id, date, work_hours, month_folder, source_file, created_at
            FROM checkin_records
            ORDER BY date
        ''')
    
    results = cursor.fetchall()
    conn.close()
    
    return [{
        'id': r[0],
        'date': r[1],
        'work_hours': r[2],
        'month_folder': r[3],
        'source_file': r[4],
        'created_at': r[5]
    } for r in results]

def update_checkin_record(record_id: int, work_hours: float):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE checkin_records SET work_hours = ? WHERE id = ?',
        (work_hours, record_id)
    )
    conn.commit()
    conn.close()

def delete_checkin_record(record_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM checkin_records WHERE id = ?', (record_id,))
    conn.commit()
    conn.close()

def save_invoice_records(records: List[Dict], month_folder: str):
    conn = get_connection()
    cursor = conn.cursor()
    
    for record in records:
        date_val = record.get('date', datetime.now())
        if isinstance(date_val, datetime):
            date_val = date_val.strftime('%Y-%m-%d')
        
        cursor.execute('''
            INSERT INTO invoice_records 
            (invoice_type, date, amount, start_location, end_location, company, source_file, invoice_file, month_folder)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            record.get('invoice_type', 'taxi'),
            date_val,
            record.get('amount', 0),
            record.get('start_location', ''),
            record.get('end_location', ''),
            record.get('company', ''),
            record.get('source_file', ''),
            record.get('invoice_file', ''),
            month_folder
        ))
    
    conn.commit()
    conn.close()

def get_invoice_records(month_folder: Optional[str] = None, invoice_type: Optional[str] = None) -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    
    query = '''
        SELECT id, invoice_type, date, amount, start_location, end_location, company, source_file, invoice_file, month_folder, created_at
        FROM invoice_records
        WHERE 1=1
    '''
    params = []
    
    if month_folder:
        query += ' AND month_folder = ?'
        params.append(month_folder)
    
    if invoice_type:
        query += ' AND invoice_type = ?'
        params.append(invoice_type)
    
    query += ' ORDER BY date'
    
    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()
    
    return [{
        'id': r[0],
        'invoice_type': r[1],
        'date': r[2],
        'amount': r[3],
        'start_location': r[4],
        'end_location': r[5],
        'company': r[6],
        'source_file': r[7],
        'invoice_file': r[8],
        'month_folder': r[9],
        'created_at': r[10]
    } for r in results]

def update_invoice_record(record_id: int, **kwargs):
    conn = get_connection()
    cursor = conn.cursor()
    
    update_fields = []
    values = []
    
    for key, value in kwargs.items():
        if key in ['amount', 'start_location', 'end_location', 'company', 'date']:
            update_fields.append(f'{key} = ?')
            if key == 'date' and isinstance(value, datetime):
                value = value.strftime('%Y-%m-%d')
            values.append(value)
    
    if update_fields:
        values.append(record_id)
        query = f"UPDATE invoice_records SET {', '.join(update_fields)} WHERE id = ?"
        cursor.execute(query, values)
        conn.commit()
    
    conn.close()

def delete_invoice_record(record_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM invoice_records WHERE id = ?', (record_id,))
    conn.commit()
    conn.close()

def save_reimburse_record(record: Dict):
    conn = get_connection()
    cursor = conn.cursor()
    
    date_val = record.get('date', datetime.now())
    if isinstance(date_val, datetime):
        date_val = date_val.strftime('%Y-%m-%d')
    
    cursor.execute('''
        INSERT INTO reimburse_records 
        (month_folder, reimburse_type, date, amount, work_hours, start_location, end_location, company, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        record.get('month_folder', ''),
        record.get('reimburse_type', ''),
        date_val,
        record.get('amount', 0),
        record.get('work_hours', 0),
        record.get('start_location', ''),
        record.get('end_location', ''),
        record.get('company', ''),
        record.get('notes', '')
    ))
    
    conn.commit()
    conn.close()

def get_reimburse_records(month_folder: Optional[str] = None) -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    
    if month_folder:
        cursor.execute('''
            SELECT id, month_folder, reimburse_type, date, amount, work_hours, start_location, end_location, company, notes, created_at
            FROM reimburse_records
            WHERE month_folder = ?
            ORDER BY date
        ''', (month_folder,))
    else:
        cursor.execute('''
            SELECT id, month_folder, reimburse_type, date, amount, work_hours, start_location, end_location, company, notes, created_at
            FROM reimburse_records
            ORDER BY date
        ''')
    
    results = cursor.fetchall()
    conn.close()
    
    return [{
        'id': r[0],
        'month_folder': r[1],
        'reimburse_type': r[2],
        'date': r[3],
        'amount': r[4],
        'work_hours': r[5],
        'start_location': r[6],
        'end_location': r[7],
        'company': r[8],
        'notes': r[9],
        'created_at': r[10]
    } for r in results]

def save_export_history(month_folder: str, export_type: str, file_path: str, record_count: int, total_amount: float):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO export_history 
        (month_folder, export_type, file_path, record_count, total_amount)
        VALUES (?, ?, ?, ?, ?)
    ''', (month_folder, export_type, file_path, record_count, total_amount))
    
    conn.commit()
    conn.close()

def get_export_history(limit: int = 20) -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, month_folder, export_type, file_path, record_count, total_amount, created_at
        FROM export_history
        ORDER BY created_at DESC
        LIMIT ?
    ''', (limit,))
    
    results = cursor.fetchall()
    conn.close()
    
    return [{
        'id': r[0],
        'month_folder': r[1],
        'export_type': r[2],
        'file_path': r[3],
        'record_count': r[4],
        'total_amount': r[5],
        'created_at': r[6]
    } for r in results]

def get_month_folders() -> List[str]:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT DISTINCT month_folder FROM (
            SELECT month_folder FROM checkin_records
            UNION
            SELECT month_folder FROM invoice_records
            UNION
            SELECT month_folder FROM reimburse_records
        )
        ORDER BY month_folder DESC
    ''')
    
    results = cursor.fetchall()
    conn.close()
    
    return [r[0] for r in results if r[0]]

def get_statistics() -> Dict:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM checkin_records')
    total_checkin = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM invoice_records')
    total_invoice = cursor.fetchone()[0]
    
    cursor.execute('SELECT COALESCE(SUM(amount), 0) FROM invoice_records')
    total_invoice_amount = cursor.fetchone()[0]
    
    cursor.execute('''
        SELECT reimburse_type, COALESCE(SUM(amount), 0) 
        FROM reimburse_records 
        GROUP BY reimburse_type
    ''')
    reimburse_by_type = {r[0]: r[1] for r in cursor.fetchall()}
    
    cursor.execute('SELECT COUNT(*) FROM export_history')
    total_exports = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        'total_checkin_records': total_checkin,
        'total_invoice_records': total_invoice,
        'total_invoice_amount': total_invoice_amount,
        'reimburse_by_type': reimburse_by_type,
        'total_exports': total_exports
    }

def clear_month_data(month_folder: str):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM checkin_records WHERE month_folder = ?', (month_folder,))
    cursor.execute('DELETE FROM invoice_records WHERE month_folder = ?', (month_folder,))
    cursor.execute('DELETE FROM reimburse_records WHERE month_folder = ?', (month_folder,))
    
    conn.commit()
    conn.close()

def clear_all_data():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM checkin_records')
    cursor.execute('DELETE FROM invoice_records')
    cursor.execute('DELETE FROM reimburse_records')
    cursor.execute('DELETE FROM export_history')
    
    conn.commit()
    conn.close()

def get_duplicate_checkin_records(month_folder: str) -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, date, work_hours, month_folder, source_file, created_at, COUNT(*) as cnt
        FROM checkin_records
        WHERE month_folder = ?
        GROUP BY date
        HAVING cnt > 1
    ''', (month_folder,))
    
    results = cursor.fetchall()
    conn.close()
    
    return [{
        'id': r[0],
        'date': r[1],
        'work_hours': r[2],
        'month_folder': r[3],
        'source_file': r[4],
        'created_at': r[5],
        'count': r[6]
    } for r in results]

def get_duplicate_invoice_records(month_folder: str) -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, date, amount, source_file, month_folder, created_at
        FROM invoice_records
        WHERE month_folder = ?
        ORDER BY date, amount, created_at
    ''', (month_folder,))
    
    results = cursor.fetchall()
    conn.close()
    
    seen = {}
    duplicates = []
    
    for r in results:
        key = (r[1], r[2])
        if key in seen:
            duplicates.append({
                'id': r[0],
                'date': r[1],
                'amount': r[2],
                'source_file': r[3],
                'month_folder': r[4],
                'created_at': r[5]
            })
        else:
            seen[key] = r[0]
    
    return duplicates

def delete_duplicate_invoice_records(month_folder: str) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, date, amount FROM invoice_records
        WHERE month_folder = ?
        ORDER BY date, amount, created_at
    ''', (month_folder,))
    
    results = cursor.fetchall()
    
    seen = {}
    ids_to_delete = []
    
    for r in results:
        key = (r[1], r[2])
        if key in seen:
            ids_to_delete.append(r[0])
        else:
            seen[key] = r[0]
    
    if ids_to_delete:
        placeholders = ','.join('?' * len(ids_to_delete))
        cursor.execute(f'DELETE FROM invoice_records WHERE id IN ({placeholders})', ids_to_delete)
        conn.commit()
    
    conn.close()
    return len(ids_to_delete)

def invoice_exists(date_str: str, amount: float, month_folder: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT COUNT(*) FROM invoice_records
        WHERE date = ? AND amount = ? AND month_folder = ?
    ''', (date_str, amount, month_folder))
    
    count = cursor.fetchone()[0]
    conn.close()
    
    return count > 0

if __name__ == '__main__':
    init_db()
    print("数据库初始化完成")
    print(f"数据库路径: {DB_PATH}")
    print(f"配置路径: {CONFIG_PATH}")
