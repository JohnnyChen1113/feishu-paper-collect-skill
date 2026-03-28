#!/usr/bin/env python3
"""One-time setup: create a Feishu Bitable with all required fields.

Usage:
  python3 setup_table.py
  python3 setup_table.py --name "my_references"
"""
import argparse
import json
import subprocess
import sys
import time


FIELDS = [
    ("文献标题", "text"),
    ("链接", "text"),
    ("作者", "text"),
    ("年份", "text"),
    ("期刊", "text"),
    ("DOI", "text"),
    ("摘要", "text"),
    ("备注", "text"),
    ("附件", "attachment"),
]


def run_lark_cli(*args):
    cmd = ["lark-cli"] + list(args)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    try:
        result = json.loads(proc.stdout)
    except (json.JSONDecodeError, ValueError):
        print(f"  lark-cli error: {proc.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    if not result.get("ok"):
        err = result.get("error", {}).get("message", "unknown error")
        print(f"  lark-cli error: {err}", file=sys.stderr)
        sys.exit(1)
    return result


def main():
    parser = argparse.ArgumentParser(description="Create Feishu Bitable for paper collection.")
    parser.add_argument("--name", default="reference", help="Base name (default: reference)")
    args = parser.parse_args()

    # Step 1: Create base
    print(f"Creating Bitable \"{args.name}\"...")
    result = run_lark_cli("base", "+base-create", "--name", args.name, "--time-zone", "Asia/Shanghai")
    base_data = result["data"]["base"]
    base_token = base_data["base_token"]
    base_url = base_data.get("url", "")
    print(f"  ✓ Base created: {base_token}")

    # Step 2: Get default table
    result = run_lark_cli("base", "+table-list", "--base-token", base_token)
    table_id = result["data"]["items"][0]["table_id"]

    # Rename default table
    run_lark_cli("base", "+table-update", "--base-token", base_token, "--table-id", table_id, "--name", args.name)
    print(f"  ✓ Table renamed to \"{args.name}\": {table_id}")

    # Step 3: Create fields
    attachment_field_id = ""
    for field_name, field_type in FIELDS:
        time.sleep(0.5)  # rate limit
        result = run_lark_cli(
            "base", "+field-create",
            "--base-token", base_token,
            "--table-id", table_id,
            "--json", json.dumps({"name": field_name, "type": field_type}),
        )
        field_id = result["data"]["field"]["id"]
        if field_name == "附件":
            attachment_field_id = field_id
        print(f"  ✓ Field \"{field_name}\" ({field_type}): {field_id}")

    # Step 4: Output config
    print()
    print("=" * 60)
    print("Setup complete! Add to your shell config (~/.zshrc or ~/.bashrc):")
    print("=" * 60)
    print()
    print(f'export FEISHU_BASE_TOKEN="{base_token}"')
    print(f'export FEISHU_TABLE_ID="{table_id}"')
    print(f'export FEISHU_ATTACHMENT_FIELD_ID="{attachment_field_id}"')
    print()
    if base_url:
        print(f"Bitable URL: {base_url}")
        print()
    print("Then run: source ~/.zshrc")
    print()
    print("Test with:")
    print(f'  python3 scripts/collect_reference.py "https://www.nature.com/articles/s41594-023-01171-9" --write --pdf')


if __name__ == "__main__":
    main()
