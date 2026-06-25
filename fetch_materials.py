#!/usr/bin/env python3
"""
fetch_materials.py - pull course content out of Canvas into ./materials

Grabs, for every active course:
  - module/wiki pages (the text readings hosted in Canvas)
  - assignment descriptions
  - uploaded files (.pdf .docx .txt .md)

Then run:  python ingest.py   to index everything.

Setup: put your Canvas token in token.txt next to this script (same token the
dashboard uses), or set CANVAS_TOKEN. Never commit or share that token.
"""

import os
import re
import sys
import json
import html as htmlmod
import urllib.request
import urllib.parse
import urllib.error
from html.parser import HTMLParser

CANVAS_URL = "https://ivylearn.ivytech.edu"
OUT_DIR = "materials"
FILE_EXTS = (".pdf", ".docx", ".txt", ".md")   # file types ingest.py can read


def get_token():
    tok = os.environ.get("CANVAS_TOKEN")
    if tok:
        return tok.strip()
    here = os.path.dirname(os.path.abspath(__file__))
    try:
        with open(os.path.join(here, "token.txt"), "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        sys.exit("No token. Put your Canvas token in token.txt or set CANVAS_TOKEN.")


TOKEN = None  # set in main


def _next_link(link_header):
    for part in (link_header or "").split(","):
        if 'rel="next"' in part:
            return part[part.find("<") + 1:part.find(">")]
    return None


def get_all(path, params=None):
    """GET that follows Canvas pagination and returns a combined list."""
    url = CANVAS_URL + path
    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=True)
    out = []
    while url:
        req = urllib.request.Request(url, headers={"Authorization": "Bearer " + TOKEN})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                link = resp.headers.get("Link", "")
        except urllib.error.HTTPError as e:
            if e.code in (401,):
                sys.exit("Canvas rejected the token (401).")
            return out  # 403/404 on a section -> just skip it
        except urllib.error.URLError:
            return out
        out.extend(data if isinstance(data, list) else [data])
        url = _next_link(link)
    return out


def get_one(path):
    req = urllib.request.Request(CANVAS_URL + path, headers={"Authorization": "Bearer " + TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def download(url, dest):
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = resp.read()
        with open(dest, "wb") as f:
            f.write(data)
        return True
    except Exception:
        return False


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self.skip = [], False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip = True
        if tag in ("p", "br", "div", "li", "h1", "h2", "h3", "tr"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = False

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def html_to_text(s):
    if not s:
        return ""
    p = _Text()
    p.feed(s)
    txt = htmlmod.unescape("".join(p.parts))
    lines = [ln.strip() for ln in txt.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def sanitize(s, maxlen=55):
    s = re.sub(r"[^\w\- ]", "", s or "").strip().replace(" ", "_")
    return (s[:maxlen] or "untitled")


def write_text(course, kind, title, text):
    if not text.strip():
        return False
    name = "%s__%s__%s.txt" % (sanitize(course, 30), kind, sanitize(title))
    with open(os.path.join(OUT_DIR, name), "w", encoding="utf-8") as f:
        f.write(text)
    return True


def main():
    global TOKEN
    TOKEN = get_token()
    os.makedirs(OUT_DIR, exist_ok=True)

    courses = get_all("/api/v1/courses", {"enrollment_state": "active", "per_page": 100})
    written = 0

    for c in courses:
        if not isinstance(c, dict) or c.get("access_restricted_by_date"):
            continue
        cid, cname = c.get("id"), c.get("name") or "course"
        if cid is None:
            continue
        print("\n== %s ==" % cname)

        # 1) wiki/module pages
        for pg in get_all("/api/v1/courses/%s/pages" % cid, {"per_page": 100}):
            slug = pg.get("url")
            if not slug:
                continue
            full = get_one("/api/v1/courses/%s/pages/%s" % (cid, slug))
            text = html_to_text((full or {}).get("body", ""))
            if write_text(cname, "page", pg.get("title", slug), text):
                written += 1
                print("  page: %s" % pg.get("title", slug))

        # 2) assignment descriptions
        for a in get_all("/api/v1/courses/%s/assignments" % cid, {"per_page": 100}):
            text = html_to_text(a.get("description", ""))
            text = ("Assignment: %s\n\n%s" % (a.get("name", ""), text)) if text else ""
            if write_text(cname, "assignment", a.get("name", "assignment"), text):
                written += 1
                print("  assignment: %s" % a.get("name", ""))

        # 3) uploaded files
        for fobj in get_all("/api/v1/courses/%s/files" % cid, {"per_page": 100}):
            fname = fobj.get("filename") or fobj.get("display_name") or ""
            ext = os.path.splitext(fname)[1].lower()
            if ext not in FILE_EXTS or not fobj.get("url"):
                continue
            dest = os.path.join(OUT_DIR, "%s__file__%s" % (sanitize(cname, 30), sanitize(os.path.splitext(fname)[0]) + ext))
            if download(fobj["url"], dest):
                written += 1
                print("  file: %s" % fname)

    print("\nWrote %d items into ./%s  ->  now run:  python ingest.py" % (written, OUT_DIR))


if __name__ == "__main__":
    main()
