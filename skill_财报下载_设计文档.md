# Skill: 财报PDF自动下载

## 概述

基于雪球 `stockn.xueqiu.com` 的无反爬虫PDF托管，实现A股/港股年报PDF的自动搜索与下载。

## 适用场景

用户提供股票代码，skill自动搜索并下载对应年报/中报PDF到本地，供后续Phase 2解析使用。

---

## 核心流程

```
输入: 股票代码 + 报告类型 + 年份
  ↓
Step 1: WebSearch 构造搜索词
  ↓
Step 2: 从结果中提取 stockn.xueqiu.com PDF链接
  ↓
Step 3: 识别完整年报（排除审计报告、摘要等）
  ↓
Step 4: Python requests 下载PDF到本地
  ↓
输出: 本地PDF文件路径
```

---

## Step 1: 搜索词构造

### A股
- 年报: `site:stockn.xueqiu.com SH{代码} 年度报告 {年份}`
- 中报: `site:stockn.xueqiu.com SH{代码} 半年度报告 {年份}`
- 深市用 `SZ` 前缀

### 港股
- 年报: `site:stockn.xueqiu.com {纯数字代码,5位补零} annual report {年份}`
- 中报: `site:stockn.xueqiu.com {代码} interim report {年份}`

### 代码前缀规则
| 市场 | 前缀 | 代码格式 | 示例 |
|------|------|----------|------|
| 沪市主板 | SH | SH600887 | 伊利股份 |
| 沪市科创板 | SH | SH688396 | 华润微 |
| 深市主板 | SZ | SZ000858 | 五粮液 |
| 深市创业板 | SZ | SZ300750 | 宁德时代 |
| 港股 | 无 | 00700 (5位补零) | 腾讯控股 |

---

## Step 2: PDF链接提取

从WebSearch结果中筛选符合以下模式的URL:
```
https://stockn.xueqiu.com/{代码}/{日期编号}.pdf
```

---

## Step 3: 年报识别逻辑

搜索结果往往会返回多个PDF（审计报告、摘要、利润分配公告等），需要识别完整年报。

### 识别规则（按优先级）

**优先选择**（完整年报特征）:
- 标题含 "年度报告" 且 **不含** "摘要"
- 标题含 "annual report" 且 **不含** "summary" / "extract"

**排除**:
- 含 "审计报告" / "auditor"
- 含 "摘要" / "summary"
- 含 "公告" / "通知" / "决议"
- 含 "利润分配" / "dividend"
- 含 "可持续发展" / "ESG" / "sustainability"
- 含 "股东大会" / "shareholders meeting"

### Fallback
如果无法从标题区分，选择文件编号中日期最接近报告发布日期（年报通常4月底发布，中报8月底发布）的那个。

---

## Step 4: Python下载代码

```python
import requests
import os

def download_annual_report(url, save_dir, stock_code, report_type, year):
    """
    下载年报PDF到本地

    Args:
        url: stockn.xueqiu.com 的PDF链接
        save_dir: 保存目录
        stock_code: 股票代码 (如 SH600887)
        report_type: "年报" 或 "中报"
        year: 报告年份 (如 2024)

    Returns:
        本地文件路径，失败返回None
    """
    filename = f"{stock_code}_{report_type}_{year}.pdf"
    filepath = os.path.join(save_dir, filename)

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) '
                       'Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://xueqiu.com/'
    }

    try:
        resp = requests.get(url, headers=headers, timeout=60, stream=True)
        resp.raise_for_status()

        # 验证是PDF
        content_type = resp.headers.get('Content-Type', '')
        if 'pdf' not in content_type.lower() and not resp.content[:5] == b'%PDF-':
            print(f"[ERROR] 返回内容不是PDF: {content_type}")
            return None

        with open(filepath, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        file_size = os.path.getsize(filepath)
        print(f"[OK] 下载完成: {filepath} ({file_size / 1024 / 1024:.1f} MB)")

        # 年报通常 > 1MB，过小可能是错误文件
        if file_size < 100 * 1024:  # < 100KB
            print(f"[WARN] 文件过小 ({file_size} bytes)，可能不是完整年报")

        return filepath

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] 下载失败: {e}")
        return None
```

---

## 输出规范

### 文件命名
```
{股票代码}_{报告类型}_{年份}.pdf
```
示例:
- `SH600887_年报_2024.pdf`
- `00700_年报_2024.pdf`
- `SH600887_中报_2025.pdf`

### 保存位置
保存到当前工作目录，路径通过返回值传递给Phase 2。

---

## 集成到Phase 1的方式

在Phase 1 prompt的数据采集流程末尾，添加以下步骤:

```
### Step N: 年报PDF下载（可选）

如果用户未提供年报PDF文件:
1. 使用WebSearch搜索: site:stockn.xueqiu.com {代码} 年度报告 {年份}
2. 从搜索结果中识别完整年报PDF链接（排除摘要/审计报告/公告）
3. 使用Python下载PDF到本地:
   pip install requests --break-system-packages (如未安装)
   执行下载代码（见skill文档）
4. 下载成功 → 在data_pack_market.md末尾记录:
   ## 附录B: 年报PDF
   - 文件路径: {filepath}
   - 来源: stockn.xueqiu.com
   - 报告类型: {年报/中报}
   - 报告年份: {year}
5. 下载失败 → 记录失败原因，coordinator提示用户手动上传
```

---

## 边界情况处理

| 情况 | 处理方式 |
|------|----------|
| WebSearch无结果 | 尝试放宽搜索词（去掉site限制），提示用户手动下载 |
| 搜索结果无stockn链接 | 记录其他来源链接供用户参考，不尝试下载 |
| 多个候选PDF | 按Step 3识别规则筛选，若仍不确定取文件最大的 |
| 下载超时 | 重试1次，仍失败则提示用户手动下载 |
| 文件过小(<100KB) | 警告可能非完整年报，仍保留但标记 |
| 港股双语年报 | 优先中文版，搜索词用中文关键词 |
| 用户已提供PDF | 跳过下载步骤，直接使用用户文件 |

---

## 依赖

- Python `requests` 库 (`pip install requests --break-system-packages`)
- WebSearch 工具（用于搜索PDF链接）

---

## 测试用例

| 股票 | 代码 | 报告 | 预期搜索词 |
|------|------|------|-----------|
| 伊利股份 | SH600887 | 2024年报 | `site:stockn.xueqiu.com SH600887 年度报告 2024` |
| 腾讯控股 | 00700 | 2024年报 | `site:stockn.xueqiu.com 00700 annual report 2024` |
| 宁德时代 | SZ300750 | 2024中报 | `site:stockn.xueqiu.com SZ300750 半年度报告 2024` |
| 长和 | 00001 | 2024年报 | `site:stockn.xueqiu.com 00001 annual report 2024` |
