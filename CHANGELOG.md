# Changelog

## v1.0 (2026-03-28)

### Features

- **Metadata extraction** from academic paper URLs with multi-layer fallback:
  - HTML meta tag parsing (citation_*, dc.*, og:*, prism.*)
  - Crossref API enrichment by DOI, title, or bibliographic fragments
  - Jina Reader fallback for blocked pages
  - bb-browser fallback for Cloudflare-protected pages (optional)
  - URL pattern parsing for OUP journals (volume/issue/page → Crossref lookup)

- **URL type detection** automatically classifies URLs as `paper` (academic) or `article` (general):
  - Academic domains (40+): Nature, Springer, OUP, Elsevier, Cell, PLOS, MDPI, arXiv, bioRxiv, CSHLP, etc.
  - General articles (WeChat, Zhihu, blogs): meta tag extraction only, no DOI regex or Crossref to avoid false positives

- **One-command write mode** (`--write`) handles the full pipeline in a single invocation:
  - Extract metadata
  - Check for duplicates (by DOI or URL)
  - Insert or update record in Feishu Bitable via lark-cli
  - Output single-line JSON result — minimal token consumption when used with AI agents

- **PDF auto-download and upload** (`--pdf`):
  - Unpaywall API for Open Access detection
  - Publisher-specific URL pattern matching (Springer, Nature, CSHLP, PLOS, MDPI, ScienceDirect)
  - PDF validation (verifies %PDF- header before upload)
  - Upload to Feishu Bitable attachment field via lark-cli
  - Automatic temp file cleanup

- **Configurable target table** via environment variables or CLI flags:
  - `FEISHU_BASE_TOKEN` / `--base-token`
  - `FEISHU_TABLE_ID` / `--table-id`
  - `FEISHU_ATTACHMENT_FIELD_ID` (env only)

- **Crossref enrichment improvements**:
  - Full journal name preference over abbreviations (container-title > short-container-title)
  - HTML entity unescaping in journal names
  - HTML/XML tag stripping and markdown italic cleanup in abstracts and titles
  - OUP journal abbreviation mapping (16 journals: nar → Nucleic Acids Research, etc.)

- **Robustness**:
  - Three-layer HTTP fetching: requests → curl → bb-browser
  - Cloudflare/bot detection and automatic fallback
  - Blocked page detection triggers Crossref URL biblio reverse-lookup
  - Duplicate prevention by DOI and URL matching

### Architecture

- Python script handles all heavy lifting (web scraping, API calls, Feishu writes via lark-cli subprocess)
- AI agent (Claude Code, etc.) only needs to run one command and read one line of output
- Token consumption reduced from 3-6K per paper to ~100-200 per paper
