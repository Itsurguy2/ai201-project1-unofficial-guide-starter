"""Stage 3: Embedding + vector store.

Embeds every chunk in chunks.jsonl with all-MiniLM-L6-v2 and writes the
vectors + metadata into a persistent ChromaDB collection (cosine space).

Run from src/:  python embed_store.py
"""

import json

import chromadb
from sentence_transformers import SentenceTransformer

from config import (
    CHROMA_DIR,
    CHUNKS_PATH,
    COLLECTION_NAME,
    EMBED_MODEL_NAME,
)


def load_chunks():
    with open(CHUNKS_PATH, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def get_collection(client):
    """Fresh collection each build so re-runs don't duplicate vectors."""
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    return client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def main():
    chunks = load_chunks()
    print(f"Loaded {len(chunks)} chunks. Loading model '{EMBED_MODEL_NAME}'...")
    model = SentenceTransformer(EMBED_MODEL_NAME)

    texts = [c["text"] for c in chunks]
    embeddings = model.encode(
        texts,
        batch_size=64,
        show_progress_bar=True,
        normalize_embeddings=True,
    )

    client = chromadb.PersistentClient(path=CHROMA_DIR)
    collection = get_collection(client)

    metadatas = [
        {
            "source": c["source"],
            "source_id": c["source_id"],
            "url": c["url"],
            "year": c["year"],
            "kind": c["kind"],
            "chunk_index": c["chunk_index"],
        }
        for c in chunks
    ]
    ids = [c["id"] for c in chunks]

    batch = 512
    for i in range(0, len(chunks), batch):
        collection.add(
            ids=ids[i:i + batch],
            documents=texts[i:i + batch],
            embeddings=embeddings[i:i + batch].tolist(),
            metadatas=metadatas[i:i + batch],
        )

    print(f"Stored {collection.count()} vectors in ChromaDB at {CHROMA_DIR}")


if __name__ == "__main__":
    main()
