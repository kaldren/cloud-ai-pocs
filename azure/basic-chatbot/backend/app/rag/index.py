"""The `docs` search index schema. The backend owns the index; Terraform creates the service."""

from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    HnswParameters,
    LexicalAnalyzerName,
    SearchableField,  # pyright: ignore[reportUnknownVariableType]  # SDK types **kw loosely
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
    SimpleField,  # pyright: ignore[reportUnknownVariableType]
    VectorSearch,
    VectorSearchAlgorithmMetric,
    VectorSearchProfile,
)

# text-embedding-3-small returns 1536 dimensions by default.
EMBEDDING_DIMENSIONS = 1536

FIELD_ID = "id"
FIELD_CONTENT = "content"
FIELD_TITLE = "title"
FIELD_SOURCE = "source"
FIELD_CHUNK_INDEX = "chunk_index"
FIELD_CONTENT_VECTOR = "content_vector"

HNSW_CONFIG_NAME = "content-hnsw"
VECTOR_PROFILE_NAME = "content-vector-profile"
SEMANTIC_CONFIG_NAME = "default"


def build_index(name: str) -> SearchIndex:
    """Index for hybrid retrieval: BM25 over `content`/`title` plus HNSW (cosine) over vectors."""
    fields: list[SearchField] = [
        SimpleField(name=FIELD_ID, type=SearchFieldDataType.STRING, key=True, filterable=True),
        SearchableField(name=FIELD_CONTENT, analyzer_name=LexicalAnalyzerName.EN_MICROSOFT),
        SearchableField(
            name=FIELD_TITLE, analyzer_name=LexicalAnalyzerName.EN_MICROSOFT, filterable=True
        ),
        SimpleField(
            name=FIELD_SOURCE, type=SearchFieldDataType.STRING, filterable=True, facetable=True
        ),
        SimpleField(
            name=FIELD_CHUNK_INDEX, type=SearchFieldDataType.INT32, filterable=True, sortable=True
        ),
        SearchField(
            name=FIELD_CONTENT_VECTOR,
            type=f"Collection({SearchFieldDataType.SINGLE.value})",
            searchable=True,
            hidden=True,  # not returned in results; keeps responses small
            vector_search_dimensions=EMBEDDING_DIMENSIONS,
            vector_search_profile_name=VECTOR_PROFILE_NAME,
        ),
    ]
    vector_search = VectorSearch(
        algorithms=[
            HnswAlgorithmConfiguration(
                name=HNSW_CONFIG_NAME,
                parameters=HnswParameters(
                    metric=VectorSearchAlgorithmMetric.COSINE,
                    m=4,
                    ef_construction=400,
                    ef_search=500,
                ),
            )
        ],
        profiles=[
            VectorSearchProfile(
                name=VECTOR_PROFILE_NAME, algorithm_configuration_name=HNSW_CONFIG_NAME
            )
        ],
    )
    semantic_search = SemanticSearch(
        default_configuration_name=SEMANTIC_CONFIG_NAME,
        configurations=[
            SemanticConfiguration(
                name=SEMANTIC_CONFIG_NAME,
                prioritized_fields=SemanticPrioritizedFields(
                    title_field=SemanticField(field_name=FIELD_TITLE),
                    content_fields=[SemanticField(field_name=FIELD_CONTENT)],
                ),
            )
        ],
    )
    return SearchIndex(
        name=name, fields=fields, vector_search=vector_search, semantic_search=semantic_search
    )


def ensure_index(client: SearchIndexClient, name: str) -> SearchIndex:
    """Create the index, or update it in place if it already exists (idempotent)."""
    return client.create_or_update_index(build_index(name))
