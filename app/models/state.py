from app.services.db import init_db, set_processing_status as _set_status
from app.services.db import get_processing_status as _get_status


def get_chroma_client():
    import chromadb
    from chromadb.config import Settings
    from app.config import CHROMA_DB_PATH
    return chromadb.PersistentClient(
        path=CHROMA_DB_PATH,
        settings=Settings(anonymized_telemetry=False),
    )


def get_chunks_collection():
    client = get_chroma_client()
    return client.get_or_create_collection(
        name="document_chunks",
        metadata={"hnsw:space": "cosine"},
    )


def get_docs_collection():
    client = get_chroma_client()
    return client.get_or_create_collection(name="documents")


def set_processing_status(doc_id: str, status: str, progress: int, message: str):
    _set_status(doc_id, status, progress, message)


def get_processing_status(doc_id: str) -> dict | None:
    return _get_status(doc_id)
