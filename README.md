# 财报下载工具 (Financial Report Downloader)

上市公司财报 PDF 自动搜索与下载工具，支持 [雪球](https://stockn.xueqiu.com)（主源）和 [同花顺](https://notice.10jqka.com.cn)（备选源），可通过 [Claude Code](https://claude.com/claude-code) 斜杠命令或 Claude 插件两种方式使用。

## 使用方法

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

# A 股中报 / 季报
/download-report 300750 2024 中报        # 宁德时代 2024 中报
/download-report 600887 2024 一季报      # 伊利股份 2024 一季报
/download-report 300750 2024 三季报      # 宁德时代 2024 三季报

# 港股
/download-report 00700 2024 年报         # 腾讯控股 2024 年报
/download-report 700 2024 interim        # 腾讯控股 2024 interim report

# 不指定年份 / 报告类型（默认最新年报）
/download-report 600887                  # 伊利股份最新年报
/download-report 300750 2024             # 宁德时代 2024 年报
```

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

## 两种使用路径

本项目提供两种使用方式，均可正常工作：

### 1. 斜杠命令（Slash Command）

在 Claude Code 中直接使用 `/download-report`，由 `.claude/commands/download-report.md` 驱动，调用 `scripts/download_report.py` 下载。

### 2. Claude 插件（Plugin）

通过 `commands/download-report.md` 入口，读取 `skills/report-download/SKILL.md` 完整工作流，调用 `skills/report-download/scripts/download_report.py` 下载。

**安装方式：** 在你的项目 `.claude/settings.json` 中添加本仓库为插件：

```json
{
  "plugins": [
    "/absolute/path/to/SKILL_financial_report_download"
  ]
}
```

添加后，Claude Code 会自动加载 `commands/` 和 `skills/` 目录，`/download-report` 命令即可使用。插件还支持自然语言触发——直接对 Claude 说"下载伊利股份2024年报"等即可自动调用。

## 项目结构

```
.
├── .claude/
│   └── commands/
│       └── download-report.md           # 斜杠命令（独立完整版，/download-report）
├── commands/
│   └── download-report.md              # Claude 插件入口
├── skills/
│   └── report-download/
│       ├── SKILL.md                     # 插件完整工作流程
│       └── scripts/
│           └── download_report.py       # Python 下载脚本（插件版）
├── scripts/
│   └── download_report.py              # Python 下载脚本（斜杠命令版）
├── requirements.txt
├── CLAUDE.md
└── README.md
```

## 依赖安装

```bash
pip install -r requirements.txt
```

仅需 `requests` 库。

## 工作流程

1. **输入解析**：解析股票代码、年份、报告类型，自动识别市场并格式化代码
2. **搜索报告**：通过 WebSearch 在 `stockn.xueqiu.com` 搜索，无结果时回退到 `notice.10jqka.com.cn`（同花顺）
3. **筛选结果**：排除摘要、审计报告等非正文文件，选择最匹配的 PDF
4. **下载文件**：通过 Python 脚本流式下载，支持重试和 PDF 格式校验

## 注意事项

- 搜索优先使用雪球（`stockn.xueqiu.com`），无结果时回退到同花顺（`notice.10jqka.com.cn`）
- 下载脚本会验证 PDF 文件头（`%PDF-` magic bytes）
- 文件小于 100KB 时会发出警告（可能为异常文件）
- 下载超时 120 秒，最多重试 3 次（渐进式退避）
- 下载文件命名格式：`{股票代码}_{报告类型}_{年份}.pdf`
