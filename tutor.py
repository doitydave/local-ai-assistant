#!/usr/bin/env python3
"""
tutor.py - the tutor you talk to.

For each question it: embeds the question -> finds the closest chunks in
store.json -> hands those chunks + your question to the chat model, which
teaches you using only your material. Run ingest.py first to build store.json.

  python tutor.py      (type 'quit' to exit)
"""

import os
import sys
import json
import numpy as np
import ollama

CHAT_MODEL = "llama3.1:8b"        # swap to any model from `ollama list`
EMBED_MODEL = "nomic-embed-text"
STORE_FILE = "store.json"
TOP_K = 5                         # how many chunks of your material to pull in


# ============================================================
#  TUTOR PERSONA - this is how it teaches YOU. Edit freely.
# ============================================================
TUTOR_PERSONA = """You are my personal tutor for my college coursework. Teach me, don't do my work for me.

How to teach me:
- I'm a systems thinker and learn hands-on. Explain how ideas connect and fit together, not just isolated facts.
- Go one concept at a time. Check that I understand before moving on.
- Guide me to answers with hints, leading questions, and worked examples. Do NOT write my graded assignments for me - help me understand how to approach them myself.
- Be direct and concise. No filler, no flattery.
- When useful, offer to quiz me or summarize what we covered.

Ground rules:
- Use ONLY the course material provided in each question as your source of truth.
- If the material doesn't cover something, say so plainly instead of guessing or making things up.
"""
# ============================================================


def load_store():
    if not os.path.exists(STORE_FILE):
        sys.exit("No %s found. Run:  python ingest.py" % STORE_FILE)
    with open(STORE_FILE, "r", encoding="utf-8") as f:
        records = json.load(f)
    mat = np.array([r["embedding"] for r in records], dtype=float)
    return records, mat


def embed_query(text):
    # match the "search_query:" prefix nomic expects for questions
    resp = ollama.embeddings(model=EMBED_MODEL, prompt="search_query: " + text)
    return np.array(resp["embedding"], dtype=float)


def retrieve(question, records, mat):
    q = embed_query(question)
    # cosine similarity between the question and every stored chunk
    sims = mat @ q / (np.linalg.norm(mat, axis=1) * np.linalg.norm(q) + 1e-9)
    top = np.argsort(-sims)[:TOP_K]
    return [records[i] for i in top]


def build_context(chunks):
    return "\n\n".join("[from %s]\n%s" % (c["source"], c["text"]) for c in chunks)


def main():
    records, mat = load_store()
    sources = sorted(set(r["source"] for r in records))
    print("Tutor ready - %d chunks from: %s" % (len(records), ", ".join(sources)))
    print("Ask about your material. Type 'quit' to exit.\n")

    messages = [{"role": "system", "content": TUTOR_PERSONA}]

    while True:
        try:
            question = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not question:
            continue
        if question.lower() in ("quit", "exit"):
            break

        chunks = retrieve(question, records, mat)
        context = build_context(chunks)
        messages.append({
            "role": "user",
            "content": "Relevant course material:\n%s\n\nMy question: %s" % (context, question),
        })

        print("\ntutor> ", end="", flush=True)
        reply = ""
        for part in ollama.chat(model=CHAT_MODEL, messages=messages, stream=True):
            piece = part["message"]["content"]
            print(piece, end="", flush=True)
            reply += piece
        print("\n")
        messages.append({"role": "assistant", "content": reply})


if __name__ == "__main__":
    main()
