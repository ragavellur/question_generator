import uuid
import os
import json

from app.config import UPLOAD_DIR
from app.services.vector_store import list_documents, get_hierarchy, delete_document as vs_delete
from app.models.state import get_docs_collection


def generate_doc_id() -> str:
    return str(uuid.uuid4())


def save_uploaded_file(filename: str, content: bytes) -> tuple[str, str]:
    doc_id = generate_doc_id()
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    safe_name = f"{doc_id}_{filename}"
    filepath = os.path.join(UPLOAD_DIR, safe_name)
    with open(filepath, "wb") as f:
        f.write(content)
    return doc_id, filepath


def get_all_documents() -> list[dict]:
    return list_documents()


def get_document_hierarchy(doc_id: str) -> list[dict]:
    return get_hierarchy(doc_id)


def remove_document(doc_id: str):
    vs_delete(doc_id)
    for fname in os.listdir(UPLOAD_DIR):
        if fname.startswith(doc_id):
            os.remove(os.path.join(UPLOAD_DIR, fname))
