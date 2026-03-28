#!/usr/bin/env python3
"""Extract metadata from a URL and optionally write to Feishu Bitable.

Usage:
  # Extract only (outputs full JSON)
  python3 collect_reference.py "<url>"

  # Extract + write to Feishu + download PDF
  python3 collect_reference.py "<url>" --write --pdf

  # Custom target table
  python3 collect_reference.py "<url>" --write --base-token XXX --table-id YYY
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.parse

import requests
from html import unescape
from html.parser import HTMLParser


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

USER_AGENT = "PaperCollect/1.0"
DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.I)
BLOCKED_TITLES = {"access denied", "just a moment...", "are you a robot?"}

DEFAULT_BASE_TOKEN = os.environ.get("FEISHU_BASE_TOKEN", "")
DEFAULT_TABLE_ID = os.environ.get("FEISHU_TABLE_ID", "")
ATTACHMENT_FIELD_ID = os.environ.get("FEISHU_ATTACHMENT_FIELD_ID", "")

ACADEMIC_DOMAINS = {
    "nature.com", "springer.com", "springerlink.com", "link.springer.com",
    "academic.oup.com", "oup.com",
    "sciencedirect.com", "elsevier.com",
    "wiley.com", "onlinelibrary.wiley.com",
    "cell.com",
    "plos.org", "journals.plos.org",
    "mdpi.com",
    "arxiv.org",
    "biorxiv.org", "medrxiv.org",
    "pubmed.ncbi.nlm.nih.gov", "ncbi.nlm.nih.gov",
    "doi.org", "dx.doi.org",
    "pnas.org",
    "science.org", "sciencemag.org",
    "acs.org", "pubs.acs.org",
    "rsc.org", "pubs.rsc.org",
    "frontiersin.org",
    "tandfonline.com",
    "sagepub.com",
    "biomedcentral.com", "bmc.com",
    "jbc.org",
    "embopress.org",
    "rupress.org",
    "elifesciences.org",
    "genetics.org",
    "plantcell.org",
    "asmjournals.org",
    "cshlp.org", "genome.cshlp.org", "genesdev.cshlp.org",
    "plantphysiol.org",
    "peerj.com",
    "royalsocietypublishing.org",
    "annualreviews.org",
    "oxfordjournals.org",
}

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# OUP journal abbreviation → full name
OUP_JOURNAL_MAP = {
    "nar": "Nucleic Acids Research",
    "bioinformatics": "Bioinformatics",
    "hmg": "Human Molecular Genetics",
    "jmcb": "Journal of Molecular Cell Biology",
    "aje": "American Journal of Epidemiology",
    "bib": "Briefings in Bioinformatics",
    "database": "Database",
    "glycob": "Glycobiology",
    "molbev": "Molecular Biology and Evolution",
    "ije": "International Journal of Epidemiology",
    "carcin": "Carcinogenesis",
    "brain": "Brain",
    "cercor": "Cerebral Cortex",
    "plcell": "The Plant Cell",
    "genetics": "Genetics",
    "g3journal": "G3: Genes, Genomes, Genetics",
}

# URL patterns for Crossref biblio fallback
URL_BIBLIO_PATTERNS = [
    (r"academic\.oup\.com/([^/]+)/article/(\d+)/(\d+)/(\d+)", ("journal", "volume", "issue", "page")),
    (r"link\.springer\.com/article/(\d+)/(\d+)/(\d+)", (None, "volume", "issue", "page")),
]

# Common PDF URL patterns by publisher
PDF_URL_PATTERNS = [
    # Springer/BMC
    (r"link\.springer\.com/article/(10\.\d+/[^?#]+)", lambda m: f"https://link.springer.com/content/pdf/{m.group(1)}.pdf"),
    # CSHLP (Genome Research, Genes & Dev)
    (r"(https?://[^/]*cshlp\.org/content/\d+/\d+/\d+)", lambda m: f"{m.group(1)}.full.pdf"),
    # Nature
    (r"(https?://www\.nature\.com/articles/[^?#]+)", lambda m: f"{m.group(1)}.pdf"),
    # PLOS
    (r"journals\.plos\.org/\w+/article\?id=(10\.\d+/[^&]+)", lambda m: f"https://journals.plos.org/plosone/article/file?id={m.group(1)}&type=printable"),
    # MDPI
    (r"(https?://www\.mdpi\.com/\d+-\d+/\d+/\d+/\d+)", lambda m: f"{m.group(1)}/pdf"),
    # eLife
    (r"elifesciences\.org/articles/(\d+)", lambda m: f"https://elifesciences.org/download/aHR0cHM6Ly9jZG4uZWxpZmVzY2llbmNlcy5vcmcvYXJ0aWNsZXMve20uZ3JvdXAoMSl9/article-{m.group(1)}.pdf"),
    # ScienceDirect — redirects via DOI
    (r"sciencedirect\.com/science/article/pii/([A-Z0-9]+)", None),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_academic_url(url):
    try:
        host = urllib.parse.urlsplit(url).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        for domain in ACADEMIC_DOMAINS:
            if host == domain or host.endswith("." + domain):
                return True
    except Exception:
        pass
    return False


class MetaParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self.meta = {}
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        attrs = {k.lower(): v for k, v in attrs if v is not None}
        if tag.lower() == "meta":
            key = (attrs.get("name") or attrs.get("property") or "").strip().lower()
            value = attrs.get("content", "").strip()
            if key and value:
                self.meta.setdefault(key, []).append(unescape(value))
        elif tag.lower() == "title":
            self.in_title = True

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data


def http_json(url):
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _is_blocked_html(html):
    if not html or len(html) < 500:
        return True
    lower = html.lower()
    for marker in BLOCKED_TITLES:
        if marker in lower:
            return True
    return False


def bb_browser_fetch(url):
    try:
        proc = subprocess.run(
            ["bb-browser", "fetch", url],
            capture_output=True, text=True, timeout=30,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout
    except Exception:
        pass
    return ""


def http_text(url):
    html = ""
    try:
        resp = requests.get(url, headers=REQUEST_HEADERS, timeout=30)
        resp.raise_for_status()
        resp.encoding = resp.encoding or "utf-8"
        html = resp.text
    except Exception:
        try:
            proc = subprocess.run(
                ["curl", "-L", "-sS", "-A", REQUEST_HEADERS["User-Agent"], url],
                check=True, capture_output=True, text=True,
            )
            html = proc.stdout
        except Exception:
            pass

    if not _is_blocked_html(html):
        return html

    bb_html = bb_browser_fetch(url)
    if bb_html and not _is_blocked_html(bb_html):
        return bb_html

    return html


def clean_space(text):
    return re.sub(r"\s+", " ", (text or "")).strip()


def first_nonempty(*values):
    for v in values:
        if v:
            return v
    return ""


def first_meta(meta, key):
    items = meta.get(key.lower(), [])
    return items[0] if items else ""


def search_doi(text):
    match = DOI_RE.search(text or "")
    return match.group(0) if match else ""


def normalize_doi(value):
    value = clean_space(value)
    if not value:
        return ""
    value = re.sub(r"^https?://(dx\.)?doi\.org/", "", value, flags=re.I)
    match = DOI_RE.search(value)
    return match.group(0) if match else value


def extract_year(value):
    match = re.search(r"\b(19|20)\d{2}\b", value or "")
    return match.group(0) if match else ""


def strip_tags(value):
    if not value:
        return ""
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"(?<!\w)_([^_]+)_(?!\w)", r"\1", value)
    return clean_space(value)


def normalize_abstract(value):
    if not value:
        return ""
    value = unescape(value)
    value = strip_tags(value)
    value = re.sub(r"^(abstract|summary)\s*[:.-]?\s*", "", value, flags=re.I)
    return value


def extract_abstract_from_jina(text):
    lines = text.splitlines()
    capture = False
    abstract_lines = []
    for line in lines:
        stripped = line.strip()
        lowered = stripped.lower()
        if lowered in {"## abstract", "# abstract", "abstract"}:
            capture = True
            continue
        if capture and stripped.startswith("#"):
            break
        if capture:
            abstract_lines.append(stripped)

    abstract = clean_space(" ".join(abstract_lines))
    if abstract:
        return normalize_abstract(abstract)

    match = re.search(
        r"\bAbstract\b[:\s]+(.+?)(?:\n#{1,6}\s|\nReferences\b|\Z)",
        text, flags=re.I | re.S,
    )
    if match:
        return normalize_abstract(match.group(1))
    return ""


# ---------------------------------------------------------------------------
# Metadata extraction
# ---------------------------------------------------------------------------

def parse_page_metadata(url, academic=True):
    html = http_text(url)
    parser = MetaParser()
    parser.feed(html)
    meta = parser.meta

    title = first_nonempty(
        first_meta(meta, "citation_title"),
        first_meta(meta, "dc.title"),
        first_meta(meta, "og:title"),
        clean_space(parser.title),
    )

    if academic:
        authors = meta.get("citation_author", []) or meta.get("dc.creator", [])
        journal = first_nonempty(
            first_meta(meta, "citation_journal_title"),
            first_meta(meta, "prism.publicationname"),
            first_meta(meta, "og:site_name"),
        )
        publication_date = first_nonempty(
            first_meta(meta, "citation_publication_date"),
            first_meta(meta, "prism.publicationdate"),
            first_meta(meta, "article:published_time"),
        )
        doi = first_nonempty(
            first_meta(meta, "citation_doi"),
            first_meta(meta, "dc.identifier"),
            search_doi(html),
        )
        volume = first_nonempty(first_meta(meta, "citation_volume"), first_meta(meta, "prism.volume"))
        issue = first_nonempty(first_meta(meta, "citation_issue"), first_meta(meta, "prism.number"))
        page = first_nonempty(
            first_meta(meta, "citation_firstpage"),
            first_meta(meta, "citation_page"),
            first_meta(meta, "citation_article_number"),
        )
    else:
        authors = meta.get("article:author", []) or meta.get("author", [])
        journal = first_nonempty(
            first_meta(meta, "og:site_name"),
            first_meta(meta, "application-name"),
        )
        publication_date = first_nonempty(
            first_meta(meta, "article:published_time"),
            first_meta(meta, "publishdate"),
            first_meta(meta, "date"),
        )
        doi = ""
        volume = ""
        issue = ""
        page = ""

    abstract = first_nonempty(
        first_meta(meta, "citation_abstract") if academic else "",
        first_meta(meta, "dc.description"),
        first_meta(meta, "og:description"),
        first_meta(meta, "description"),
    )

    if not title or clean_space(title).lower() in BLOCKED_TITLES or not abstract:
        jina = parse_jina_metadata(url)
        title = jina.get("title", "") or title
        authors = authors or jina.get("authors", [])
        journal = first_nonempty(journal, jina.get("journal", ""))
        publication_date = first_nonempty(publication_date, jina.get("publication_date", ""))
        abstract = first_nonempty(abstract, jina.get("abstract", ""))

    return {
        "title": clean_space(title),
        "authors": [clean_space(a) for a in authors if clean_space(a)],
        "journal": clean_space(journal),
        "publication_date": clean_space(publication_date),
        "year": extract_year(publication_date),
        "doi": normalize_doi(doi),
        "volume": clean_space(volume),
        "issue": clean_space(issue),
        "page": clean_space(page),
        "abstract": normalize_abstract(abstract),
        "source_url": url,
    }


def parse_jina_metadata(url):
    text = http_text("https://r.jina.ai/" + url)
    title = ""
    authors = []
    journal = ""
    publication_date = ""
    abstract = extract_abstract_from_jina(text)

    for line in text.splitlines():
        stripped = clean_space(line)
        if not stripped:
            continue
        if stripped.startswith("Title: "):
            title = stripped[len("Title: "):]
        elif stripped == "by":
            continue
        elif stripped.startswith("Submission received:") and "Published:" in stripped:
            publication_date = stripped.split("Published:", 1)[1].strip()
        elif not journal:
            match = re.search(r"/journal/([a-z0-9-]+)", stripped, re.I)
            if match:
                journal = match.group(1).replace("-", " ").title()

    author_block = re.search(r"\nby\s+(.*?)\nDepartment of ", text, flags=re.S)
    if author_block:
        author_text = clean_space(author_block.group(1))
        author_text = re.sub(r"\[\!\[Image.*?\]\(.*?\)\]", "", author_text)
        author_text = re.sub(r"\[\]\(mailto:.*?\)", "", author_text)
        author_text = clean_space(author_text.replace(" and ", "; "))
        authors = [clean_space(x) for x in author_text.split(";") if clean_space(x)]
        authors = [re.sub(r"\s*\(https?://[^)]+\)", "", x).replace("*", "").strip() for x in authors]

    return {
        "title": title,
        "authors": authors,
        "journal": journal,
        "publication_date": publication_date,
        "abstract": abstract,
    }


# ---------------------------------------------------------------------------
# Crossref
# ---------------------------------------------------------------------------

def parse_url_biblio(url):
    for pattern, keys in URL_BIBLIO_PATTERNS:
        m = re.search(pattern, url)
        if not m:
            continue
        result = {}
        for i, key in enumerate(keys):
            if key:
                result[key] = m.group(i + 1)
        if result.get("journal"):
            abbr = result["journal"].lower()
            if abbr in OUP_JOURNAL_MAP:
                result["journal"] = OUP_JOURNAL_MAP[abbr]
        return result
    return {}


def crossref_by_biblio(biblio):
    journal = biblio.get("journal", "")
    volume = biblio.get("volume", "")
    page = biblio.get("page", "")
    if not (volume and page):
        return {}
    api_url = "https://api.crossref.org/works?"
    filters = []
    if journal and len(journal) > 5:
        filters.append("container-title:" + journal)
    if filters:
        api_url += "filter=" + urllib.parse.quote(",".join(filters)) + "&"
    query = " ".join(filter(None, [volume, page]))
    api_url += "query.bibliographic=" + urllib.parse.quote(query) + "&rows=5"
    try:
        items = http_json(api_url)["message"].get("items", [])
    except Exception:
        return {}
    for item in items:
        item_vol = item.get("volume", "")
        item_page = item.get("page", "").split("-")[0]
        if item_vol == volume and item_page == page:
            return crossref_to_fields(item)
    return {}


def crossref_by_doi(doi):
    if not doi:
        return {}
    work = http_json(
        "https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="")
    )["message"]
    return crossref_to_fields(work)


def crossref_by_title(title):
    if not title:
        return {}
    url = (
        "https://api.crossref.org/works?query.title="
        + urllib.parse.quote(title)
        + "&rows=1"
    )
    items = http_json(url)["message"].get("items", [])
    return crossref_to_fields(items[0]) if items else {}


def crossref_to_fields(work):
    authors = []
    for item in work.get("author", []):
        full = clean_space(" ".join(filter(None, [item.get("given", ""), item.get("family", "")])))
        if full:
            authors.append(full)

    year = ""
    for key in ("published-print", "published-online", "published"):
        parts = work.get(key, {}).get("date-parts", [])
        if parts and parts[0]:
            year = str(parts[0][0])
            break

    full_journal = clean_space(" ".join(work.get("container-title") or []))
    short_journal = clean_space(" ".join(work.get("short-container-title") or []))
    journal = unescape(full_journal or short_journal)

    return {
        "title": strip_tags(" ".join(work.get("title", []))),
        "authors": authors,
        "journal": journal,
        "year": year,
        "doi": normalize_doi(work.get("DOI", "")),
        "volume": clean_space(work.get("volume", "")),
        "issue": clean_space(work.get("issue", "")),
        "page": clean_space(work.get("page", "")),
        "abstract": normalize_abstract(work.get("abstract", "")),
    }


# ---------------------------------------------------------------------------
# Merge & format
# ---------------------------------------------------------------------------

def merge_metadata(primary, fallback):
    merged = dict(primary)
    for key, value in fallback.items():
        if key == "authors":
            if not merged.get(key) and value:
                merged[key] = value
        elif not merged.get(key) and value:
            merged[key] = value
    return merged


def build_note(data):
    parts = []
    if data.get("volume"):
        parts.append(f"Vol. {data['volume']}")
    if data.get("issue"):
        parts.append(f"Issue {data['issue']}")
    if data.get("page"):
        label = "Pages" if "-" in data["page"] else "Article"
        parts.append(f"{label} {data['page']}")
    return ", ".join(parts)


def to_feishu_fields(data):
    return {
        "文献标题": data.get("title", ""),
        "链接": data.get("source_url", ""),
        "作者": "; ".join(data.get("authors", [])),
        "年份": data.get("year", ""),
        "期刊": data.get("journal", ""),
        "DOI": data.get("doi", ""),
        "摘要": data.get("abstract", ""),
        "备注": build_note(data),
    }


def extract_metadata(url):
    """Full extraction pipeline: page scrape → Crossref enrichment → merge."""
    academic = is_academic_url(url)
    page_data = parse_page_metadata(url, academic=academic)

    if academic:
        scraped_title = clean_space(page_data.get("title", ""))
        is_page_blocked = (
            not scraped_title
            or scraped_title.lower() in BLOCKED_TITLES
            or (not page_data.get("abstract") and not page_data.get("doi"))
        )

        crossref_data = {}
        if page_data.get("doi"):
            crossref_data = crossref_by_doi(page_data["doi"])

        if is_page_blocked and not crossref_data:
            biblio = parse_url_biblio(url)
            if biblio:
                crossref_data = crossref_by_biblio(biblio)

        if not crossref_data and page_data.get("title") and not is_page_blocked:
            crossref_data = crossref_by_title(page_data["title"])

        if is_page_blocked and crossref_data:
            merged = merge_metadata(crossref_data, page_data)
        else:
            merged = merge_metadata(page_data, crossref_data)
        if crossref_data.get("journal") and len(crossref_data["journal"]) > len(merged.get("journal", "")):
            merged["journal"] = crossref_data["journal"]
    else:
        merged = page_data

    merged["source_url"] = url
    return "paper" if academic else "article", merged


# ---------------------------------------------------------------------------
# Feishu write (via lark-cli subprocess)
# ---------------------------------------------------------------------------

def lark_cli(*args):
    """Run a lark-cli command and return parsed JSON output."""
    cmd = ["lark-cli"] + list(args)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    try:
        result = json.loads(proc.stdout)
    except (json.JSONDecodeError, ValueError):
        result = {}
    if proc.returncode != 0 or not result.get("ok"):
        err = result.get("error", {}).get("message", proc.stderr.strip())
        raise RuntimeError(f"lark-cli failed: {err}")
    return result


def find_duplicate(base_token, table_id, doi, url):
    """Check existing records for a duplicate by DOI or URL."""
    result = lark_cli(
        "base", "+record-list",
        "--base-token", base_token,
        "--table-id", table_id,
        "--limit", "200",
    )
    data = result.get("data", {})
    fields_list = data.get("fields", [])
    records = data.get("data", [])
    record_ids = data.get("record_id_list", [])

    doi_idx = fields_list.index("DOI") if "DOI" in fields_list else -1
    link_idx = fields_list.index("链接") if "链接" in fields_list else -1

    for i, row in enumerate(records):
        if doi and doi_idx >= 0 and row[doi_idx] and normalize_doi(str(row[doi_idx])) == normalize_doi(doi):
            return record_ids[i], "DOI"
        if url and link_idx >= 0 and row[link_idx] and clean_space(str(row[link_idx])) == clean_space(url):
            return record_ids[i], "链接"
    return None, None


def upsert_record(base_token, table_id, fields, record_id=None):
    """Insert or update a record."""
    args = [
        "base", "+record-upsert",
        "--base-token", base_token,
        "--table-id", table_id,
        "--json", json.dumps(fields, ensure_ascii=False),
    ]
    if record_id:
        args += ["--record-id", record_id]
    result = lark_cli(*args)
    rid = result.get("data", {}).get("record", {}).get("record_id_list", [""])[0]
    if not rid:
        rid = record_id or ""
    return rid


def guess_pdf_url(source_url, doi):
    """Try to construct a direct PDF URL from publisher patterns or Unpaywall."""
    # Try Unpaywall first
    if doi:
        try:
            uw = http_json(f"https://api.unpaywall.org/v2/{doi}?email=paper_collect@tool.local")
            pdf_url = (uw.get("best_oa_location") or {}).get("url_for_pdf")
            if pdf_url:
                return pdf_url
        except Exception:
            pass

    # Try publisher URL patterns
    for pattern, builder in PDF_URL_PATTERNS:
        m = re.search(pattern, source_url)
        if m and builder:
            return builder(m)

    # ScienceDirect: use DOI redirect to get PDF
    if "sciencedirect.com" in source_url and doi:
        return f"https://doi.org/{doi}"

    return ""


def download_pdf(pdf_url, filename):
    """Download PDF to a temp directory, return local path or empty string."""
    tmpdir = tempfile.mkdtemp(prefix="paper_")
    local_path = os.path.join(tmpdir, filename)
    try:
        resp = requests.get(pdf_url, headers=REQUEST_HEADERS, timeout=60, stream=True, allow_redirects=True)
        resp.raise_for_status()
        with open(local_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        # Verify it's actually a PDF
        with open(local_path, "rb") as f:
            header = f.read(5)
        if header != b"%PDF-":
            os.remove(local_path)
            return ""
        return local_path
    except Exception:
        return ""


def upload_attachment(base_token, table_id, record_id, field_id, file_path):
    """Upload a file to a Bitable attachment field."""
    # lark-cli requires relative path — cd into the directory
    dirpath = os.path.dirname(file_path)
    filename = os.path.basename(file_path)
    cmd = [
        "lark-cli", "base", "+record-upload-attachment",
        "--base-token", base_token,
        "--table-id", table_id,
        "--record-id", record_id,
        "--field-id", field_id,
        "--file", f"./{filename}",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=dirpath)
    try:
        result = json.loads(proc.stdout)
    except (json.JSONDecodeError, ValueError):
        return False
    return result.get("ok", False)


def make_pdf_filename(metadata):
    """Generate PDF filename: FirstAuthor_Year_Journal.pdf"""
    authors = metadata.get("authors", [])
    first_author = authors[0].split(",")[0].split()[-1] if authors else "Unknown"
    year = metadata.get("year", "")
    journal = metadata.get("journal", "").replace(" ", "_").replace("&", "and")[:30]
    parts = [p for p in [first_author, year, journal] if p]
    return "_".join(parts) + ".pdf"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Extract metadata from a URL.")
    parser.add_argument("url", help="Paper or article URL")
    parser.add_argument("--write", action="store_true", help="Write to Feishu Bitable")
    parser.add_argument("--pdf", action="store_true", help="Download and attach PDF (requires --write)")
    parser.add_argument("--base-token", default=DEFAULT_BASE_TOKEN, help="Feishu base token")
    parser.add_argument("--table-id", default=DEFAULT_TABLE_ID, help="Feishu table ID")
    args = parser.parse_args()

    # Step 1: Extract metadata
    url_type, metadata = extract_metadata(args.url)
    fields = to_feishu_fields(metadata)

    if not args.write:
        # Extract-only mode: output full JSON
        result = {"type": url_type, "metadata": metadata, "fields": fields}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    # Step 2: Check for duplicates
    record_id, matched_on = find_duplicate(args.base_token, args.table_id, metadata.get("doi"), args.url)

    # Step 3: Insert or update
    if record_id:
        action = "updated"
        upsert_record(args.base_token, args.table_id, fields, record_id=record_id)
    else:
        action = "inserted"
        record_id = upsert_record(args.base_token, args.table_id, fields)

    result = {
        "status": action,
        "record_id": record_id,
        "type": url_type,
        "title": metadata.get("title", ""),
        "doi": metadata.get("doi", ""),
        "journal": metadata.get("journal", ""),
        "year": metadata.get("year", ""),
    }
    if matched_on:
        result["matched_on"] = matched_on

    # Step 4: PDF download and upload
    if args.pdf and url_type == "paper":
        pdf_url = guess_pdf_url(args.url, metadata.get("doi", ""))
        if pdf_url:
            filename = make_pdf_filename(metadata)
            local_path = download_pdf(pdf_url, filename)
            if local_path:
                ok = upload_attachment(args.base_token, args.table_id, record_id, ATTACHMENT_FIELD_ID, local_path)
                result["pdf"] = "uploaded" if ok else "upload_failed"
                os.remove(local_path)
                # Clean up temp dir
                try:
                    os.rmdir(os.path.dirname(local_path))
                except OSError:
                    pass
            else:
                result["pdf"] = "download_failed"
        else:
            result["pdf"] = "no_pdf_url"
    elif args.pdf and url_type != "paper":
        result["pdf"] = "skipped_non_paper"

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False))
        sys.exit(1)
