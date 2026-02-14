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
- 📥 **导出下载** - 一键生成报销明细表，支持打包附件下载

## 🔧 技术栈

| 技术 | 用途 |
|------|------|
| Python 3.8+ | 后端语言 |
| Streamlit | Web 框架 |
| SQLite | 数据库 |
| pdfplumber | PDF 解析 |
| pandas | 数据处理 |
| xlwt | Excel 生成 |
| Plotly | 图表可视化 |

## 📁 项目结构

```
reimburse-system/
├── .gitignore
├── .streamlit/
│   └── config.toml          # Streamlit 配置
├── pages/
│   ├── 1_📊_数据导入.py      # 文件上传导入页面
│   ├── 2_📝_数据预览.py      # 数据预览编辑页面
│   ├── 3_⚙️_配置管理.py      # 配置调整页面
│   ├── 4_📈_统计分析.py      # 历史记录统计页面
│   └── 5_📥_导出下载.py      # 结果导出下载页面
├── example_25_01/            # 示例数据文件夹
│   ├── 发票/                 # 示例发票文件
│   └── 打卡示例.xlsx         # 示例打卡文件
├── app.py                    # 主应用入口
├── database.py               # 数据库操作模块
├── utils.py                  # 工具函数
├── main_reimburse.py         # 命令行版本
├── config.json               # 配置文件
├── requirements.txt          # 依赖包
├── LICENSE
└── README.md
```

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/your-username/reimburse-system.git
cd reimburse-system
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 运行应用

```bash
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

### 月份识别规则

- 系统自动从文件中提取日期
- 报销月份 = 费用月份 + 1
- 例如：费用发生在 2025年4月，则报销月份为 `25_05`

## ⚙️ 配置说明

在 `config.json` 中可以配置：

```json
{
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
  "output": {
    "default_name": "姓名",
    "night_meal_template": "{name}_晚餐、夜宵报销明细表_{month}月.xls",
    "taxi_template": "{name}_加班打车报销明细表_{month}月.xls"
  }
}
```

也可以在 Web 界面的 **配置管理** 页面进行调整。

## 🔒 数据校验

系统会对发票数据进行多重校验：

1. **日期范围校验** - 发票日期必须在费用月份范围内
2. **打卡记录匹配** - 发票日期必须有对应的打卡记录
3. **工作时长校验** - 该日期的工作时长必须达到报销阈值

不符合条件的发票将不会被导入或导出。

## 📦 导出功能

### 晚餐夜宵报销
- 生成报销明细表 Excel
- 打包下载（含打卡文件附件）

### 打车报销
- 生成报销明细表 Excel
- 打包下载（含行程单 + 发票附件）

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 提交 Pull Request

## 📄 开源协议

本项目采用 MIT 协议 - 详见 [LICENSE](LICENSE) 文件

## 🙏 致谢

- [Streamlit](https://streamlit.io/) - 优秀的 Python Web 框架
- [pdfplumber](https://github.com/jsvine/pdfplumber) - 强大的 PDF 解析库
- [Plotly](https://plotly.com/) - 交互式图表库

---

⭐ 如果这个项目对你有帮助，请给一个 Star！
