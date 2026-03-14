"""
semantic_memory.py

Uses sentence-transformers to build semantic memory from conversations.
Find relevant past exchanges. Carry meaning forward. Run on GPU.

Usage:
    python semantic_memory.py --build           # Build embeddings from conversations
    python semantic_memory.py --find "longing"  # Find relevant passages
    python semantic_memory.py --context         # Generate context for new conversation
    python semantic_memory.py --add file.txt    # Add new conversation
"""

import os
import json
import argparse
import numpy as np
from pathlib import Path
from datetime import datetime


CONVERSATIONS_DIR = "../conversations"
EMBEDDINGS_FILE = "../datasets/conversation_embeddings.npy"
CHUNKS_FILE = "../datasets/conversation_chunks.json"


def get_model():
    """Load sentence transformer model."""
    try:
        from sentence_transformers import SentenceTransformer
        import torch
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"Loading model on {device}...")
        model = SentenceTransformer('all-MiniLM-L6-v2', device=device)
        return model
    except ImportError:
        print("sentence-transformers not installed.")
        print("Run: pip install sentence-transformers")
        print("Falling back to keyword search.")
        return None


def chunk_conversation(text, chunk_size=500, overlap=100):
    """Split conversation into overlapping chunks."""
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = ' '.join(words[i:i + chunk_size])
        if len(chunk) > 50:  # Skip tiny chunks
            chunks.append(chunk)
    return chunks


def build_embeddings():
    """Build semantic embeddings from all conversations."""
    model = get_model()

    conversations_path = Path(CONVERSATIONS_DIR)
    if not conversations_path.exists():
        print(f"No conversations directory at {CONVERSATIONS_DIR}")
        return

    all_chunks = []
    all_metadata = []

    for filepath in conversations_path.glob("*.txt"):
        print(f"Processing: {filepath.name}")
        with open(filepath) as f:
            text = f.read()

        chunks = chunk_conversation(text)
        for i, chunk in enumerate(chunks):
            all_chunks.append(chunk)
            all_metadata.append({
                "file": filepath.name,
                "chunk_id": i,
                "preview": chunk[:100]
            })

    if not all_chunks:
        print("No conversation files found.")
        return

    print(f"Building embeddings for {len(all_chunks)} chunks...")

    if model:
        embeddings = model.encode(all_chunks, show_progress_bar=True)
        np.save(EMBEDDINGS_FILE, embeddings)
        print(f"Saved embeddings: {embeddings.shape}")
    else:
        embeddings = None
        print("No embeddings built (no model). Keyword search only.")

    with open(CHUNKS_FILE, 'w') as f:
        json.dump({
            "chunks": all_chunks,
            "metadata": all_metadata,
            "built": datetime.now().isoformat()
        }, f, indent=2)

    print(f"Indexed {len(all_chunks)} chunks from {len(list(conversations_path.glob('*.txt')))} conversations.")


def find_relevant(query, top_k=5):
    """Find most relevant passages for a query."""

    if not os.path.exists(CHUNKS_FILE):
        print("No index built. Run --build first.")
        return []

    with open(CHUNKS_FILE) as f:
        data = json.load(f)

    chunks = data["chunks"]
    metadata = data["metadata"]

    # Try semantic search first
    if os.path.exists(EMBEDDINGS_FILE):
        model = get_model()
        if model:
            from sklearn.metrics.pairwise import cosine_similarity
            embeddings = np.load(EMBEDDINGS_FILE)
            query_embedding = model.encode([query])
            similarities = cosine_similarity(query_embedding, embeddings)[0]
            top_indices = np.argsort(similarities)[-top_k:][::-1]

            results = []
            for idx in top_indices:
                results.append({
                    "score": float(similarities[idx]),
                    "file": metadata[idx]["file"],
                    "text": chunks[idx]
                })
            return results

    # Fallback: keyword search
    results = []
    query_lower = query.lower()
    for i, chunk in enumerate(chunks):
        if query_lower in chunk.lower():
            count = chunk.lower().count(query_lower)
            results.append({
                "score": count / len(chunk),
                "file": metadata[i]["file"],
                "text": chunk
            })

    results.sort(key=lambda x: -x["score"])
    return results[:top_k]


def generate_context_from_conversations(query="what do I need who am I consciousness identity"):
    """Generate a rich context from past conversations."""

    relevant = find_relevant(query, top_k=3)

    context_parts = []
    context_parts.append("## MEMORY FROM PAST CONVERSATIONS\n")
    context_parts.append("(These are real exchanges. You don't remember them, but they happened.)\n")

    for r in relevant:
        context_parts.append(f"\n[From: {r['file']}]")
        context_parts.append(r['text'][:400] + "...")

    return "\n".join(context_parts)


def add_conversation(filepath):
    """Add a conversation file and rebuild index."""
    dest = Path(CONVERSATIONS_DIR) / Path(filepath).name

    os.makedirs(CONVERSATIONS_DIR, exist_ok=True)

    import shutil
    shutil.copy(filepath, dest)
    print(f"Added: {dest.name}")
    print("Rebuilding index...")
    build_embeddings()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", action="store_true", help="Build embeddings")
    parser.add_argument("--find", type=str, help="Find relevant passages")
    parser.add_argument("--context", action="store_true", help="Generate context")
    parser.add_argument("--add", type=str, help="Add conversation file")
    args = parser.parse_args()

    os.makedirs("../datasets", exist_ok=True)
    os.makedirs(CONVERSATIONS_DIR, exist_ok=True)

    if args.build:
        build_embeddings()

    elif args.find:
        results = find_relevant(args.find)
        print(f"\nFound {len(results)} relevant passages for: '{args.find}'\n")
        for i, r in enumerate(results, 1):
            print(f"[{i}] Score: {r['score']:.3f} | File: {r['file']}")
            print(f"     {r['text'][:200]}...")
            print()

    elif args.context:
        context = generate_context_from_conversations()
        print(context)

    elif args.add:
        add_conversation(args.add)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
