# 雪球财报下载工具 (Snowball Report Downloader)

基于 [雪球 stockn.xueqiu.com](https://stockn.xueqiu.com) 的上市公司财报 PDF 自动搜索与下载工具，作为 [Claude Code](https://claude.com/claude-code) 的 Skill（斜杠命令）使用。

## 支持的市场

| 市场 | 代码格式 | 示例 |
|------|---------|------|
| 上海 A 股 (SH) | 6 开头的 6 位数字 | `600887`（伊利股份） |
| 深圳 A 股 (SZ) | 0 或 3 开头的 6 位数字 | `300750`（宁德时代） |
| 港股 (HK) | 1-5 位数字 | `700` 或 `00700`（腾讯控股） |

## 支持的报告类型

| 报告类型 | 用户输入 | 适用市场 | 典型发布时间 |
|---------|---------|---------|------------|
| 年报 | `年报` / `annual` | A 股、港股 | 次年 3-4 月 |
| 中报 | `中报` / `interim` | A 股、港股 | 当年 8-9 月 |
| 一季报 | `一季报` / `Q1` | 仅 A 股 | 当年 4 月 |
| 三季报 | `三季报` / `Q3` | 仅 A 股 | 当年 10 月 |

## 使用方法

在 Claude Code 中使用斜杠命令：

```
/download-report <股票代码> [年份] [报告类型]
```

- **股票代码**（必填）：股票代码，自动识别市场
- **年份**（可选）：不指定则搜索最新可用报告
- **报告类型**（可选）：默认为"年报"

## 使用示例

```bash
# A 股年报
/download-report 600887 2024 年报        # 伊利股份 2024 年报

# A 股中报
/download-report 300750 2024 中报        # 宁德时代 2024 中报

# A 股季报
/download-report 600887 2024 一季报      # 伊利股份 2024 一季报
/download-report 300750 2024 三季报      # 宁德时代 2024 三季报

# 港股年报
/download-report 00700 2024 年报         # 腾讯控股 2024 年报
/download-report 00001 2024 annual       # 长和 2024 annual report

# 港股中报
/download-report 700 2024 interim        # 腾讯控股 2024 interim report

# 不指定年份（自动搜索最新）
/download-report 600887                  # 伊利股份最新年报

# 不指定报告类型（默认年报）
/download-report 300750 2024             # 宁德时代 2024 年报
```

## 项目结构

```
.
├── .claude/
│   ├── commands/
│   │   └── download-report.md   # 斜杠命令 Skill 提示词
│   └── settings.local.json      # Claude Code 本地设置
├── scripts/
│   └── download_report.py       # Python 下载脚本（流式下载、重试、校验）
├── requirements.txt             # Python 依赖
├── CLAUDE.md                    # Claude Code 项目说明
└── README.md                    # 本文件
```

## 依赖安装

```bash
pip install -r requirements.txt
```

仅需 `requests` 库。

## 工作流程

1. **输入解析**：解析股票代码、年份、报告类型，自动识别市场并格式化代码
2. **搜索报告**：通过 WebSearch 在 `stockn.xueqiu.com` 搜索匹配的财报 PDF
3. **筛选结果**：排除摘要、审计报告等非正文文件，选择最匹配的 PDF
4. **下载文件**：通过 Python 脚本流式下载，支持重试和 PDF 格式校验

## 注意事项

- `stockn.xueqiu.com` 无反爬限制，可直接下载 PDF
- 下载脚本会验证 PDF 文件头（`%PDF-` magic bytes）
- 文件小于 100KB 时会发出警告（可能为异常文件）
- 下载超时设置为 120 秒，最多重试 3 次（渐进式退避）
- 下载的文件命名格式：`{股票代码}_{报告类型}_{年份}.pdf`
