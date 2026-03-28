---
name: reference-intake
description: Extract metadata from a paper or article URL and save it into a Feishu Bitable. Supports academic papers (with Crossref enrichment) and general articles (WeChat, Zhihu, blog posts, etc.). Use when the user gives one or more links and asks to collect, extract, record, or save information.
---

# Reference Intake

Turn a URL into a normalized row in 飞书多维表格.

## Quick Usage

```bash
# One command does everything: extract → dedup → write → PDF
python3 ~/feishu_paper_collect_skill/scripts/collect_reference.py "<url>" --write --pdf

# Custom target table
python3 ~/feishu_paper_collect_skill/scripts/collect_reference.py "<url>" --write --pdf \
  --base-token <BASE_TOKEN> --table-id <TABLE_ID>

# Extract only (no write, outputs full JSON)
python3 ~/feishu_paper_collect_skill/scripts/collect_reference.py "<url>"
```

## Configuration

Set target table via environment variables:

```bash
export FEISHU_BASE_TOKEN="your_base_token"
export FEISHU_TABLE_ID="your_table_id"
export FEISHU_ATTACHMENT_FIELD_ID="your_attachment_field_id"
```

Or pass via CLI flags `--base-token` and `--table-id`.

## Output Format

With `--write`, the script outputs a single-line JSON:

```json
{"status":"inserted","record_id":"recXXX","type":"paper","title":"...","doi":"...","journal":"...","year":"...","pdf":"uploaded"}
```

Possible `status` values: `inserted`, `updated`, `error`
Possible `pdf` values: `uploaded`, `download_failed`, `upload_failed`, `no_pdf_url`, `skipped_non_paper`

Without `--write`, outputs full JSON with `type`, `metadata`, and `fields` keys.

## URL Type Detection

The script auto-detects URL type:
- **`paper`** (academic domains): full DOI extraction, Crossref enrichment, PDF download
- **`article`** (everything else): meta tag extraction only, no DOI/Crossref, no PDF

## Multiple Links

Process links one by one. If the user sends several links, run the script for each and summarize results at the end.

## Dependencies

- **Python 3** + `requests`
- **lark-cli** — Feishu Bitable read/write
- **bb-browser** (optional) — fallback for Cloudflare-blocked pages
