import os
from pinecone import Pinecone, ServerlessSpec

_embedding_model = None

def _get_model():
    global _embedding_model
    if _embedding_model is None:
        hf_token = os.getenv("HF_TOKEN")
        if hf_token:
            os.environ["HF_TOKEN"] = hf_token
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    return _embedding_model


_pc    = None
_index = None

def _get_index():
    global _pc, _index
    if _index is not None:
        return _index

    PINECONE_API_KEY   = os.getenv("PINECONE_API_KEY")
    PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "code-review-platform")

    if not PINECONE_API_KEY:
        print("[Pinecone] No API key found in environment.")
        return None

    try:
        _pc = Pinecone(api_key=PINECONE_API_KEY)
        existing = [i["name"] for i in _pc.list_indexes()]
        if PINECONE_INDEX_NAME not in existing:
            _pc.create_index(
                name=PINECONE_INDEX_NAME,
                dimension=384,
                metric='cosine',
                spec=ServerlessSpec(cloud='aws', region='us-east-1')
            )
        _index = _pc.Index(PINECONE_INDEX_NAME)
        print(f"[Pinecone] Connected to index '{PINECONE_INDEX_NAME}'")
    except Exception as e:
        print(f"[Pinecone] Init failed: {e}")
    return _index


def create_embedding(text: str) -> list:
    return _get_model().encode(text).tolist()


def split_into_chunks(text: str, chunk_size: int = 500) -> list:
    words = text.split()
    chunks, current, length = [], [], 0
    for word in words:
        current.append(word)
        length += len(word) + 1
        if length >= chunk_size:
            chunks.append(" ".join(current))
            current, length = [], 0
    if current:
        chunks.append(" ".join(current))
    return chunks


def store_vectors(project_id: int, user_id: int, file_id: int,
                  file_name: str, file_path: str, content: str):
    idx = _get_index()
    if not idx:
        print("[Pinecone] Not initialized — skipping vector storage.")
        return 0

    chunks  = split_into_chunks(content)
    vectors = []
    for i, chunk in enumerate(chunks):
        embedding = create_embedding(chunk)
        vectors.append({
            "id":     f"proj_{project_id}_file_{file_id}_chunk_{i}",
            "values": embedding,
            "metadata": {
                "project_id": int(project_id),
                "user_id":    int(user_id),
                "file_id":    int(file_id),       
                "file_name":  file_name,
                "file_path":  file_path,
                "chunk_text": chunk,
            }
        })

    if vectors:
        try:
            ns = f"project_{project_id}"
            idx.upsert(vectors=vectors, namespace=ns)
            print(f"[Pinecone] Upserted {len(vectors)} vectors for '{file_name}' in ns={ns}")
            return len(vectors)
        except Exception as e:
            print(f"[Pinecone] Upsert error: {e}")
    return 0


def search_vectors(project_id: int, file_ids: list,
                   query: str, top_k: int = 5) -> list:
    idx = _get_index()
    if not idx:
        print("[Pinecone] Not initialized — returning empty.")
        return []

    query_embedding = create_embedding(query)
    ns = f"project_{project_id}"

    if file_ids:
        filter_dict = {"file_id": {"$in": [int(fid) for fid in file_ids]}}
    else:
        filter_dict = None

    try:
        results = idx.query(
            vector=query_embedding,
            filter=filter_dict,
            namespace=ns,
            top_k=top_k,
            include_metadata=True,
        )
        matches = results.get("matches", [])
        print(f"[Pinecone] ns={ns} filter={filter_dict} → {len(matches)} matches")

        if not matches and filter_dict:
            print(f"[Pinecone] Filter returned 0 — retrying without file_id filter")
            results2 = idx.query(
                vector=query_embedding,
                namespace=ns,
                top_k=top_k,
                include_metadata=True,
            )
            matches = results2.get("matches", [])
            print(f"[Pinecone] No-filter retry → {len(matches)} matches")

        return [m.get("metadata", {}) for m in matches]

    except Exception as e:
        print(f"[Pinecone] Search error: {e}")
        return []

def delete_project_vectors(project_id: int):
    idx = _get_index()
    if not idx:
        return
    try:
        ns = f"project_{project_id}"
        idx.delete(delete_all=True, namespace=ns)
        print(f"[Pinecone] Deleted all vectors in ns={ns}")
    except Exception as e:
        print(f"[Pinecone] Delete error: {e}")