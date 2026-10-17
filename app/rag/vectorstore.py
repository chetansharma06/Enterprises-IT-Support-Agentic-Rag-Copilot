import time
from pinecone import Pinecone , ServerlessSpec
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_pinecone import PineconeVectorStore
from app.core.config import get_settings
from app.core.network import external_call

settings = get_settings()


_embeddings = None
_vectorstore = None


EMBEDDING_DIMENSION = 384



def get_embedding_dimension(model_name: str | None = None) -> int:
    return EMBEDDING_DIMENSION



def get_embeddings():
    global _embeddings
    if _embeddings is None:
        _embeddings = external_call(
            "huggingface.co",
            "loading the embedding model",
            lambda: HuggingFaceEmbeddings(
                model_name=settings.embedding_model,
                model_kwargs={"device": "cpu", "local_files_only": settings.hf_hub_offline},
                encode_kwargs={"normalize_embeddings": True},
            ),
        )
    return _embeddings




def ensure_index():
    if not settings.pinecone_api_key:
        raise RuntimeError("PINECONE_API_KEY is missing")

    desired_dimension = get_embedding_dimension()
    pc = Pinecone(api_key=settings.pinecone_api_key)
    names = external_call("api.pinecone.io", "listing Pinecone indexes", lambda: [x["name"] for x in pc.list_indexes()])

    if settings.pinecone_index_name in names:
        index_info = external_call("api.pinecone.io", "describing the Pinecone index", lambda: pc.describe_index(settings.pinecone_index_name))
        current_dimension = getattr(index_info, "dimension", None)
        if current_dimension is None and isinstance(index_info, dict):
            current_dimension = index_info.get("dimension")

        if current_dimension is not None and current_dimension != desired_dimension:
            external_call("api.pinecone.io", "deleting the incompatible Pinecone index", lambda: pc.delete_index(name=settings.pinecone_index_name))
            while settings.pinecone_index_name in external_call("api.pinecone.io", "checking Pinecone index deletion", lambda: [x["name"] for x in pc.list_indexes()]):
                time.sleep(1)

    if settings.pinecone_index_name not in external_call("api.pinecone.io", "checking for the Pinecone index", lambda: [x["name"] for x in pc.list_indexes()]):
        external_call("api.pinecone.io", "creating the Pinecone index", lambda: pc.create_index(
                name=settings.pinecone_index_name,
                dimension=desired_dimension,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1"),
            ))
        while not external_call("api.pinecone.io", "waiting for the Pinecone index", lambda: pc.describe_index(settings.pinecone_index_name).status["ready"]):
            time.sleep(1)

    return external_call("api.pinecone.io", "opening the Pinecone index", lambda: pc.Index(settings.pinecone_index_name))





def get_vectorstore():
    global _vectorstore
    if _vectorstore is None:
        index = ensure_index()
        _vectorstore = PineconeVectorStore(
            index=index,
            embedding=get_embeddings(),
            namespace=settings.pinecone_namespace,
        )
    return _vectorstore



def get_retriever():
    return get_vectorstore().as_retriever(search_kwargs={"k": settings.top_k})



def add_documents(chunks):
    store = get_vectorstore()
    return external_call("api.pinecone.io", "upserting document vectors", lambda: store.add_documents(chunks))
