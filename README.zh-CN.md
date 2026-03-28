# feishu-paper-collect-skill

一条命令，把论文 URL 变成飞书多维表格里的一行记录（含 PDF 附件）。

```bash
python3 scripts/collect_reference.py "https://www.nature.com/articles/s41594-023-01171-9" --write --pdf
# {"status":"inserted","record_id":"recXXX","type":"paper","title":"...","pdf":"uploaded"}
```

## 功能

- **学术论文**：自动提取元数据 + Crossref 交叉验证 + PDF 下载上传
- **一般文章**：微信公众号、知乎、博客等也能收录
- **40+ 学术出版商**：Nature、Springer、Cell、OUP、Elsevier、arXiv、bioRxiv 等
- **反爬兜底**：requests → curl → bb-browser 三层 fallback
- **省 Token**：一条命令、一行输出，专为 AI Agent 设计

## 快速上手（从零开始）

### 第 1 步：安装基础工具

```bash
# Python 依赖
pip install requests

# lark-cli（飞书命令行工具）
npm install -g lark-cli

# bb-browser（可选，用于绕过反爬）
npm install -g bb-browser
```

### 第 2 步：登录飞书

```bash
lark-cli auth login
```

按提示在浏览器里完成飞书账号授权。

### 第 3 步：克隆本仓库

```bash
git clone https://github.com/JohnnyChen1113/feishu-paper-collect-skill.git
cd feishu-paper-collect-skill
```

### 第 4 步：创建飞书多维表格

运行初始化脚本，它会自动帮你创建多维表格和所有字段：

```bash
python3 scripts/setup_table.py
```

脚本会输出类似这样的内容：

```
✓ 多维表格「reference」已创建
✓ 9 个字段已创建

请将以下内容添加到你的 shell 配置文件（~/.zshrc 或 ~/.bashrc）：

export FEISHU_BASE_TOKEN="JuPGbxxxxxx"
export FEISHU_TABLE_ID="tblXxxxxxx"
export FEISHU_ATTACHMENT_FIELD_ID="fldXxxxxxx"
```

按照输出的提示，把三行 `export` 添加到你的 shell 配置文件里，然后：

```bash
source ~/.zshrc  # 或 source ~/.bashrc
```

### 第 5 步：测试

```bash
# 试一篇论文
python3 scripts/collect_reference.py "https://www.nature.com/articles/s41594-023-01171-9" --write --pdf
```

看到 `"status":"inserted"` 就成功了，去飞书多维表格里检查一下。

## 使用方式

```bash
# 只提取元数据（不写入飞书，输出完整 JSON）
python3 scripts/collect_reference.py "<url>"

# 提取 + 写入飞书
python3 scripts/collect_reference.py "<url>" --write

# 提取 + 写入 + 下载 PDF
python3 scripts/collect_reference.py "<url>" --write --pdf

# 指定其他多维表格
python3 scripts/collect_reference.py "<url>" --write --base-token XXX --table-id YYY
```

## 输出格式

`--write` 模式输出单行 JSON：

```json
{"status":"inserted","record_id":"recXXX","type":"paper","title":"...","doi":"...","journal":"...","year":"...","pdf":"uploaded"}
```

| 字段 | 可能的值 |
|------|---------|
| `status` | `inserted`（新增）、`updated`（更新）、`error`（失败） |
| `type` | `paper`（学术论文）、`article`（一般文章） |
| `pdf` | `uploaded`、`download_failed`、`no_pdf_url`、`skipped_non_paper` |

## 多维表格字段说明

| 字段名 | 类型 | 说明 |
|--------|------|------|
| 文献标题 | 文本 | 论文/文章标题（主键） |
| 链接 | 文本 | 来源 URL |
| 作者 | 文本 | 作者列表，用 `; ` 分隔 |
| 年份 | 文本 | 4 位年份 |
| 期刊 | 文本 | 期刊名或网站名 |
| DOI | 文本 | 不含 `https://doi.org/` 前缀 |
| 摘要 | 文本 | 摘要或描述 |
| 备注 | 文本 | 卷号、期号、页码 |
| 附件 | 附件 | PDF 文件 |

## 搭配 Claude Code 使用

把本仓库放在你的工作目录下，Claude Code 会自动识别 `SKILL.md`。之后你只需要说：

> "帮我收录这篇论文 https://..."

Claude 就会调用脚本完成所有操作。

## 常见问题

**Q: 提示 lark-cli 权限不足？**
A: 确保你对目标多维表格有编辑权限。用 `setup_table.py` 创建的表默认有权限。

**Q: PDF 下载失败？**
A: 部分出版商的 PDF 需要机构登录。安装 bb-browser 并在 Chrome 里登录机构账号，脚本会自动用你的浏览器身份下载。

**Q: 微信公众号文章的 DOI 显示为空？**
A: 正常行为。非学术内容不提取 DOI，避免假阳性。

**Q: 出版商不在识别列表里？**
A: 在 `scripts/collect_reference.py` 的 `ACADEMIC_DOMAINS` 集合里添加域名即可。

## License

MIT
