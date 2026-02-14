# 💰 报销管理系统

一个基于 Streamlit 的自动化报销管理系统，用于处理加班打车和夜宵晚餐报销。

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28%2B-red)](https://streamlit.io/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

## ✨ 功能特性

- 📊 **数据导入** - 上传打卡 Excel 和发票 PDF 文件，自动解析入库
- 📝 **数据预览** - 查看、编辑、删除打卡和发票记录
- ⚙️ **配置管理** - 灵活调整报销阈值、金额、文件命名规则
- 📈 **统计分析** - 月度报销统计、发票分析、历史记录图表
- 📥 **导出下载** - 一键生成报销明细表

## 🔧 技术栈

| 技术 | 用途 |
|------|------|
| Python 3.8+ | 后端语言 |
| Streamlit | Web 框架 |
| SQLite | 数据库（本地存储） |
| pdfplumber | PDF 解析 |
| pandas | 数据处理 |
| xlwt | Excel 生成 |
| Plotly | 图表可视化 |

## 📁 项目结构

```
Auto_Reimbursement/
├── src/                       # 源代码
│   ├── app.py                 # 主入口
│   ├── database.py            # 数据库模块
│   ├── utils.py               # 工具函数
│   ├── main_reimburse.py      # 命令行版本
│   └── pages/                 # Streamlit 页面
│       ├── 1_📊_数据导入.py
│       ├── 2_📝_数据预览.py
│       ├── 3_⚙️_配置管理.py
│       ├── 4_📈_统计分析.py
│       └── 5_📥_导出下载.py
├── data/                      # 数据目录（不上传 Git）
│   ├── db/                    # 数据库文件
│   ├── config/                # 配置文件
│   └── uploads/               # 上传文件
├── output/                    # 导出文件（不上传 Git）
├── .streamlit/
│   └── config.toml
├── requirements.txt
├── .gitignore
├── LICENSE
└── README.md
```

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/Kangkangnice/Auto_Reimbursement.git
cd Auto_Reimbursement
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 运行应用

```bash
cd src
streamlit run app.py
```

应用将在 http://localhost:8501 启动

## 📖 使用说明

### 报销规则

| 报销类型 | 条件 | 金额 |
|---------|------|------|
| 晚餐 | 工作时长 ≥ 9.5 小时 | ¥18 |
| 夜宵 | 工作时长 ≥ 12 小时 | ¥20 |
| 打车 | 工作时长 ≥ 11 小时 | 按实际发票金额 |

### 文件要求

**打卡文件：**
- 格式：Excel (.xlsx/.xls)
- 需包含工作时长列
- 文件名建议含"打卡"

**发票文件：**
- 格式：PDF
- 高德打车电子行程单 + 电子发票
- 支持批量上传

### 使用流程

1. **数据导入** - 上传打卡文件和发票文件
2. **数据预览** - 检查导入的数据，可编辑修改
3. **配置管理** - 根据需要调整报销规则
4. **统计分析** - 查看报销统计数据
5. **导出下载** - 生成报销明细表并下载

## 🔒 数据安全

- **本地存储** - 所有数据存储在本地 SQLite 数据库
- **无网络传输** - 数据不经过任何外部服务器
- **隐私保护** - `data/` 目录不上传到 Git

## 📄 开源协议

本项目采用 MIT 协议 - 详见 [LICENSE](LICENSE) 文件

## 🙏 致谢

- [Streamlit](https://streamlit.io/) - 优秀的 Python Web 框架
- [pdfplumber](https://github.com/jsvine/pdfplumber) - 强大的 PDF 解析库
- [Plotly](https://plotly.com/) - 交互式图表库

---

⭐ 如果这个项目对你有帮助，请给一个 Star！
