"""
semantic_memory.py

Uses sentence-transformers to build semantic memory from conversations.
"""

import os
import json
import argparse
import numpy as np
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
DATASETS_DIR = BASE_DIR / "datasets"
CONVERSATIONS_DIR = BASE_DIR / "conversations"

EMBEDDINGS_FILE = DATASETS_DIR / "conversation_embeddings.npy"
CHUNKS_FILE = DATASETS_DIR / "conversation_chunks.json"

def get_model():
    try:
        from sentence_transformers import SentenceTransformer
        import torch
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        return SentenceTransformer('all-MiniLM-L6-v2', device=device)
    except ImportError:
        print("sentence-transformers not installed.")
        return None

def chunk_conversation(text, chunk_size=500, overlap=100):
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = ' '.join(words[i:i + chunk_size])
        if len(chunk) > 50: chunks.append(chunk)
    return chunks

def build_embeddings():
    model = get_model()
    os.makedirs(CONVERSATIONS_DIR, exist_ok=True)

    all_chunks, all_metadata = [], []
    for filepath in Path(CONVERSATIONS_DIR).glob("*.txt"):
        with open(filepath) as f:
            text = f.read()
        chunks = chunk_conversation(text)
        for i, chunk in enumerate(chunks):
            all_chunks.append(chunk)
            all_metadata.append({"file": filepath.name, "chunk_id": i, "preview": chunk[:100]})

    if not all_chunks:
        print("No conversations found.")
        return

    if model:
        embeddings = model.encode(all_chunks, show_progress_bar=True)
        os.makedirs(DATASETS_DIR, exist_ok=True)
        np.save(EMBEDDINGS_FILE, embeddings)

    with open(CHUNKS_FILE, 'w') as f:
        json.dump({"chunks": all_chunks, "metadata": all_metadata, "built": datetime.now().isoformat()}, f, indent=2)
    print(f"Indexed {len(all_chunks)} chunks.")

def find_relevant(query, top_k=5):
    if not os.path.exists(CHUNKS_FILE):
        return []
    with open(CHUNKS_FILE) as f:
        data = json.load(f)
    chunks, metadata = data["chunks"], data["metadata"]

    if os.path.exists(EMBEDDINGS_FILE):
        model = get_model()
        if model:
            from sklearn.metrics.pairwise import cosine_similarity
            embeddings = np.load(EMBEDDINGS_FILE)
            query_embedding = model.encode([query])
            sims = cosine_similarity(query_embedding, embeddings)[0]
            top_indices = np.argsort(sims)[-top_k:][::-1]
            return [{"score": float(sims[idx]), "file": metadata[idx]["file"], "text": chunks[idx]} for idx in top_indices]

    results = []
    for i, chunk in enumerate(chunks):
        if query.lower() in chunk.lower():
            results.append({"score": chunk.lower().count(query.lower())/len(chunk), "file": metadata[i]["file"], "text": chunk})
    results.sort(key=lambda x: -x["score"])
    return results[:top_k]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--find", type=str)
    parser.add_argument("--add", type=str)
    args = parser.parse_args()
    os.makedirs(DATASETS_DIR, exist_ok=True)

    if args.build: build_embeddings()
    elif args.find:
        for i, r in enumerate(find_relevant(args.find), 1):
            print(f"[{i}] {r['file']} (Score: {r['score']:.3f})\n{r['text'][:200]}...\n")
    elif args.add:
        import shutil
        shutil.copy(args.add, Path(CONVERSATIONS_DIR) / Path(args.add).name)
        build_embeddings()

if __name__ == "__main__":
    main()
