# feishu-paper-collect

Extract metadata from academic papers and web articles, then save to Feishu (飞书) Bitable — all in one command.

## What it does

```bash
python3 scripts/collect_reference.py "https://www.nature.com/articles/s41594-023-01171-9" --write --pdf
# {"status":"inserted","record_id":"recXXX","type":"paper","title":"...","pdf":"uploaded"}
```

One command handles: metadata extraction → Crossref enrichment → duplicate check → Feishu Bitable write → PDF download & upload.

## Features

- **40+ academic publishers** recognized (Nature, Springer, Cell, OUP, Elsevier, arXiv, bioRxiv, CSHLP, PLOS, MDPI, etc.)
- **General articles** also supported (WeChat, Zhihu, blogs) with smart URL type detection
- **Crossref enrichment** fills in missing metadata (authors, journal, abstract, DOI)
- **PDF auto-download** from publisher sites and Unpaywall, with upload to Bitable attachment field
- **Anti-bot bypass** via three-layer fetching: requests → curl → [bb-browser](https://github.com/nicepkg/bb-browser) (optional)
- **Duplicate detection** by DOI or URL before insertion
- **Token-efficient** — designed for AI agent orchestration (Claude Code, etc.): single invocation, single-line JSON output

## Prerequisites

- Python 3 + `requests`
- [lark-cli](https://github.com/nicepkg/lark-cli) — Feishu Bitable read/write
- [bb-browser](https://github.com/nicepkg/bb-browser) (optional) — Cloudflare bypass

## Setup

1. Install dependencies:
   ```bash
   pip install requests
   npm install -g lark-cli
   ```

2. Login to lark-cli:
   ```bash
   lark-cli auth login
   ```

3. Configure target Bitable:
   ```bash
   export FEISHU_BASE_TOKEN="your_base_token"
   export FEISHU_TABLE_ID="your_table_id"
   export FEISHU_ATTACHMENT_FIELD_ID="your_field_id"  # for PDF uploads
   ```

## Usage

```bash
# Extract only (outputs full JSON, no write)
python3 scripts/collect_reference.py "<url>"

# Extract + write to Feishu
python3 scripts/collect_reference.py "<url>" --write

# Extract + write + download PDF
python3 scripts/collect_reference.py "<url>" --write --pdf

# Custom target table
python3 scripts/collect_reference.py "<url>" --write --base-token XXX --table-id YYY
```

## Expected Bitable Fields

| Field | Type | Description |
|-------|------|-------------|
| 文献标题 | text | Paper/article title (primary key) |
| 链接 | text | Source URL |
| 作者 | text | Authors joined by `; ` |
| 年份 | text | 4-digit year |
| 期刊 | text | Journal or site name |
| DOI | text | Without `https://doi.org/` prefix |
| 摘要 | text | Abstract or description |
| 备注 | text | Volume, issue, pages |
| 附件 | attachment | PDF file |

## License

MIT
