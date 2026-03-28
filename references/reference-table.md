# Reference Table

Configure the target Feishu Bitable via environment variables or CLI flags:

```bash
export FEISHU_BASE_TOKEN="your_base_token_here"
export FEISHU_TABLE_ID="your_table_id_here"
export FEISHU_ATTACHMENT_FIELD_ID="your_attachment_field_id_here"
```

Or pass via CLI:

```bash
python3 collect_reference.py "<url>" --write --base-token <token> --table-id <id>
```

Base token can be extracted from the Bitable URL: `https://*.feishu.cn/base/<base-token>`

## Expected fields

- `文献标题` — primary key (first column)
- `链接`
- `作者`
- `年份`
- `期刊`
- `DOI`
- `摘要`
- `备注`
- `附件` (attachment type) — PDF files
