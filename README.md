# Local AI Assistant

A private, fully offline AI assistant. It runs a local large language model with retrieval-augmented generation (RAG) over your own documents — nothing leaves your machine.

## What it does
- Ingests your documents (PDF, DOCX, TXT, Markdown), splits them into chunks, and embeds them locally.
- Answers questions grounded in those documents using semantic search plus a local LLM.
- Runs entirely offline via [Ollama](https://ollama.com) — no API keys, no cloud, no data sent out.
- Two interfaces: a terminal chat and a Flask web UI.

## Tech stack
- **Python**
- **Ollama** — local LLM runtime (chat + embedding models)
- **nomic-embed-text** — document/query embeddings
- **NumPy** — cosine-similarity retrieval
- **Flask** — web interface

## How it works
1. `ingest.py` reads documents from `./materials`, chunks them, embeds each chunk, and writes a local vector store (`store.json`).
2. On a query, the question is embedded and compared (cosine similarity) against the store to retrieve the most relevant chunks.
3. Those chunks are passed as context to a local LLM via Ollama, which answers grounded in the source material.

## Files
- `ingest.py` — document loading, chunking, embedding, store creation
- `tutor.py` — terminal chat (retrieval + local LLM)
- `app.py` — Flask web interface
- `fetch_materials.py` — optional: pulls source documents from a Canvas LMS account via API

## Setup
```bash
# 1. Install Ollama, then pull the models
ollama pull llama3.1:8b
ollama pull nomic-embed-text

# 2. Python environment
python -m venv .venv
source .venv/bin/activate
pip install ollama numpy pypdf python-docx flask

# 3. Add documents to ./materials, then build the index
python ingest.py

# 4. Run it
python tutor.py     # terminal interface
python app.py       # web UI at localhost:5000
```

## Privacy
Everything runs locally. Your documents, the embeddings, and the model all stay on your machine — no external calls.
