#!/usr/bin/env python3
"""
ingest.py - Step 1 of the tutor pipeline.

Reads every document in ./materials, splits each into overlapping chunks,
turns each chunk into an embedding (a vector) using Ollama's nomic-embed-text,
and saves everything to store.json. Re-run this whenever you add or change
course materials.

Pipeline:  read files -> chunk text -> embed chunks -> save index
"""

import os
import sys
import json
import ollama

MATERIALS_DIR = "materials"     # drop your PDFs / Word docs / notes here
STORE_FILE = "store.json"       # the searchable index this script builds
EMBED_MODEL = "nomic-embed-text"
CHUNK_SIZE = 800                # characters per chunk
CHUNK_OVERLAP = 120             # characters shared between neighboring chunks


# ---------- reading different file types ----------
def read_pdf(path):
    from pypdf import PdfReader
    reader = PdfReader(path)
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def read_docx(path):
    import docx
    d = docx.Document(path)
    return "\n".join(p.text for p in d.paragraphs)


def read_txt(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


READERS = {".pdf": read_pdf, ".docx": read_docx, ".txt": read_txt, ".md": read_txt}


# ---------- splitting text into overlapping chunks ----------
def chunk_text(text):
    text = " ".join(text.split())          # collapse whitespace/newlines
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start:start + CHUNK_SIZE])
        start += CHUNK_SIZE - CHUNK_OVERLAP  # step forward, keeping an overlap
    return [c for c in chunks if c.strip()]


# ---------- turning text into a vector ----------
def embed(text):
    # nomic recommends a "search_document:" prefix for stored chunks
    resp = ollama.embeddings(model=EMBED_MODEL, prompt="search_document: " + text)
    return resp["embedding"]


def main():
    if not os.path.isdir(MATERIALS_DIR):
        os.makedirs(MATERIALS_DIR)
        sys.exit("Created ./%s — drop your course files in it and run again." % MATERIALS_DIR)

    records = []
    files = sorted(os.listdir(MATERIALS_DIR))
    if not files:
        sys.exit("./%s is empty — add some PDFs, Word docs, or notes first." % MATERIALS_DIR)

    for name in files:
        path = os.path.join(MATERIALS_DIR, name)
        ext = os.path.splitext(name)[1].lower()
        reader = READERS.get(ext)
        if reader is None:
            print("  skip (unsupported): %s" % name)
            continue
        try:
            text = reader(path)
        except Exception as e:
            print("  skip (read error): %s (%s)" % (name, e))
            continue

        chunks = chunk_text(text)
        print("  %s -> %d chunks" % (name, len(chunks)))
        for i, ch in enumerate(chunks):
            records.append({"text": ch, "source": name, "chunk": i,
                            "embedding": embed(ch)})

    if not records:
        sys.exit("No readable content found. Supported: .pdf .docx .txt .md")

    with open(STORE_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f)

    print("\nIndexed %d chunks from %d file(s) -> %s"
          % (len(records), len(set(r["source"] for r in records)), STORE_FILE))


if __name__ == "__main__":
    main()
