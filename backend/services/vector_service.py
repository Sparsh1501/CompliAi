"""
Vector Database Service for Qdrant Integration
Handles embedding generation and vector storage for semantic search.
"""
import logging
from typing import List, Dict, Optional
import uuid

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    QdrantClient = None

from .multi_llm_service_new import MultiLLMService

logger = logging.getLogger(__name__)


class VectorService:
    """Service for managing vector embeddings in Qdrant."""

    def __init__(self, qdrant_client: Optional[QdrantClient] = None, llm_service: Optional[MultiLLMService] = None):
        """
        Initialize Vector Service.

        Args:
            qdrant_client: Optional Qdrant client instance (uses in-memory if not provided)
            llm_service: Optional LLM service for generating embeddings
        """
        self.qdrant_client = qdrant_client
        self.llm_service = llm_service or MultiLLMService()
        self.collection_name = "policy_clauses"
        self.vector_size = 384  # Default embedding dimension for sentence-transformers

        if not QDRANT_AVAILABLE:
            logger.warning("Qdrant client not available - vector operations will be disabled")
        elif self.qdrant_client:
            self._ensure_collection()

    def _ensure_collection(self):
        """Ensure the policy_clauses collection exists in Qdrant."""
        if not self.qdrant_client:
            return

        try:
            # Check if collection exists
            collections = self.qdrant_client.get_collections()
            collection_names = [c.name for c in collections.collections]

            if self.collection_name not in collection_names:
                # Create collection with vector configuration
                self.qdrant_client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.vector_size,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"Created Qdrant collection: {self.collection_name}")
            else:
                logger.info(f"Qdrant collection already exists: {self.collection_name}")
        except Exception as e:
            logger.error(f"Failed to ensure collection: {e}", exc_info=True)

    async def store_policy_clauses(
        self,
        policy_id: str,
        clauses: List[Dict],
        organization: str,
        user_id: str
    ) -> int:
        """
        Store policy clause embeddings in Qdrant.

        Args:
            policy_id: Unique policy identifier
            clauses: List of clause dictionaries with 'clause_id', 'text', etc.
            organization: Organization identifier
            user_id: User identifier

        Returns:
            Number of clauses stored successfully
        """
        if not self.qdrant_client:
            logger.warning("Qdrant client not available - skipping vector storage")
            return 0

        try:
            points = []
            stored_count = 0

            for clause in clauses:
                clause_text = clause.get('text') or clause.get('original_text', '')
                clause_id = clause.get('clause_id', str(uuid.uuid4()))

                if not clause_text:
                    logger.warning(f"Skipping clause {clause_id} - no text content")
                    continue

                # Generate embedding for clause text
                embedding = await self.llm_service.generate_embeddings(clause_text)

                # Ensure embedding has correct dimension
                if len(embedding) != self.vector_size:
                    logger.warning(
                        f"Embedding size mismatch: got {len(embedding)}, expected {self.vector_size}. "
                        "Padding or truncating."
                    )
                    if len(embedding) < self.vector_size:
                        # Pad with zeros
                        embedding = embedding + [0.0] * (self.vector_size - len(embedding))
                    else:
                        # Truncate
                        embedding = embedding[:self.vector_size]

                # Create point with metadata
                point = PointStruct(
                    id=str(uuid.uuid4()),  # Unique point ID
                    vector=embedding,
                    payload={
                        'policy_id': policy_id,
                        'clause_id': clause_id,
                        'text': clause_text,
                        'section': clause.get('section'),
                        'page_number': clause.get('page_number'),
                        'title': clause.get('title'),
                        'requirement_type': clause.get('requirement_type', 'informational'),
                        'subject_category': clause.get('subject_category', 'general'),
                        'criticality': clause.get('criticality', 'medium'),
                        'organization': organization,
                        'user_id': user_id,
                        'tags': clause.get('tags', []),
                        'keywords': clause.get('keywords', [])
                    }
                )
                points.append(point)
                stored_count += 1

            # Batch upsert to Qdrant
            if points:
                self.qdrant_client.upsert(
                    collection_name=self.collection_name,
                    points=points
                )
                logger.info(f"Stored {stored_count} clause embeddings for policy {policy_id}")

            return stored_count

        except Exception as e:
            logger.error(f"Failed to store policy clauses in Qdrant: {e}", exc_info=True)
            return 0

    async def store_regulation_clauses(
        self,
        regulation_id: str,
        clauses: List[Dict],
        organization: str,
        user_id: str
    ) -> int:
        """
        Store regulation clause embeddings in the regulation_clauses Qdrant collection.

        Args:
            regulation_id: Unique regulation identifier
            clauses: List of clause dictionaries with 'clause_id', 'text', etc.
            organization: Organization identifier
            user_id: User identifier

        Returns:
            Number of clauses stored successfully
        """
        collection_name = "regulation_clauses"
        if not self.qdrant_client:
            logger.warning("Qdrant client not available - skipping regulation vector storage")
            return 0

        try:
            # Ensure the regulation_clauses collection exists
            try:
                collections = self.qdrant_client.get_collections()
                collection_names = [c.name for c in collections.collections]
                if collection_name not in collection_names:
                    from qdrant_client.models import VectorParams, Distance as QDistance
                    self.qdrant_client.create_collection(
                        collection_name=collection_name,
                        vectors_config=VectorParams(
                            size=self.vector_size,
                            distance=QDistance.COSINE
                        )
                    )
                    logger.info(f"Created Qdrant collection: {collection_name}")
            except Exception as e:
                logger.warning(f"Could not verify collection: {e}")

            points = []
            stored_count = 0

            for clause in clauses:
                clause_text = clause.get('text') or clause.get('original_text', '')
                clause_id = clause.get('clause_id', str(uuid.uuid4()))

                if not clause_text:
                    logger.warning(f"Skipping clause {clause_id} - no text content")
                    continue

                # Generate embedding for clause text
                embedding = await self.llm_service.generate_embeddings(clause_text)

                # Ensure embedding has correct dimension
                if len(embedding) != self.vector_size:
                    logger.warning(
                        f"Embedding size mismatch: got {len(embedding)}, expected {self.vector_size}. "
                        "Padding or truncating."
                    )
                    if len(embedding) < self.vector_size:
                        embedding = embedding + [0.0] * (self.vector_size - len(embedding))
                    else:
                        embedding = embedding[:self.vector_size]

                # Create point with regulation-specific metadata
                point = PointStruct(
                    id=str(uuid.uuid4()),  # Unique point ID
                    vector=embedding,
                    payload={
                        'regulation_id': regulation_id,
                        'clause_id': clause_id,
                        'text': clause_text,
                        'section': clause.get('section'),
                        'page_number': clause.get('page_number'),
                        'title': clause.get('title'),
                        'requirement_type': clause.get('requirement_type', 'mandatory'),
                        'subject_category': clause.get('subject_category', 'general'),
                        'criticality': clause.get('criticality', 'high'),
                        'organization': organization,
                        'user_id': user_id,
                        'tags': clause.get('tags', []),
                        'keywords': clause.get('keywords', [])
                    }
                )
                points.append(point)
                stored_count += 1

            # Batch upsert to Qdrant regulation_clauses collection
            if points:
                self.qdrant_client.upsert(
                    collection_name=collection_name,
                    points=points
                )
                logger.info(f"Stored {stored_count} regulation clause embeddings for regulation {regulation_id}")

            return stored_count

        except Exception as e:
            logger.error(f"Failed to store regulation clauses in Qdrant: {e}", exc_info=True)
            return 0

    async def search_regulation_clauses(
        self,
        query_text: str,
        organization: str,
        limit: int = 10,
        score_threshold: float = 0.3,
        regulation_id: Optional[str] = None
    ) -> List[Dict]:
        """
        Search for similar regulation clauses using semantic similarity.

        Args:
            query_text: Search query text
            organization: Organization filter
            limit: Maximum number of results
            score_threshold: Minimum similarity score (0-1)
            regulation_id: Optional regulation ID filter

        Returns:
            List of similar regulation clauses with scores
        """
        collection_name = "regulation_clauses"
        if not self.qdrant_client:
            logger.warning("Qdrant client not available - returning empty results")
            return []

        try:
            # Generate embedding for query
            query_embedding = await self.llm_service.generate_embeddings(query_text)

            # Ensure embedding has correct dimension
            if len(query_embedding) != self.vector_size:
                if len(query_embedding) < self.vector_size:
                    query_embedding = query_embedding + [0.0] * (self.vector_size - len(query_embedding))
                else:
                    query_embedding = query_embedding[:self.vector_size]

            # Build filter conditions
            filter_conditions = [
                FieldCondition(
                    key="organization",
                    match=MatchValue(value=organization)
                )
            ]

            if regulation_id:
                filter_conditions.append(
                    FieldCondition(
                        key="regulation_id",
                        match=MatchValue(value=regulation_id)
                    )
                )

            # Search in Qdrant regulation_clauses collection (using query_points for qdrant-client >= 1.16)
            query_response = self.qdrant_client.query_points(
                collection_name=collection_name,
                query=query_embedding,
                query_filter=Filter(must=filter_conditions) if filter_conditions else None,
                limit=limit,
                score_threshold=score_threshold
            )
            search_results = query_response.points if hasattr(query_response, 'points') else []

            # Format results
            results = []
            for result in search_results:
                results.append({
                    'clause_id': result.payload.get('clause_id'),
                    'regulation_id': result.payload.get('regulation_id'),
                    'text': result.payload.get('text'),
                    'section': result.payload.get('section'),
                    'title': result.payload.get('title'),
                    'score': result.score,
                    'requirement_type': result.payload.get('requirement_type'),
                    'subject_category': result.payload.get('subject_category'),
                    'criticality': result.payload.get('criticality'),
                    'tags': result.payload.get('tags', []),
                    'keywords': result.payload.get('keywords', [])
                })

            logger.info(f"Found {len(results)} similar regulation clauses for query")
            return results

        except Exception as e:
            logger.error(f"Failed to search regulation clauses: {e}", exc_info=True)
            return []

    async def get_regulation_collection_stats(self) -> Dict:
        """
        Get statistics about the regulation_clauses vector collection.

        Returns:
            Dictionary with collection statistics
        """
        collection_name = "regulation_clauses"
        if not self.qdrant_client:
            return {'available': False, 'error': 'Qdrant client not available'}

        try:
            collection_info = self.qdrant_client.get_collection(collection_name)
            # Handle both old and new Qdrant client versions
            vectors_count = getattr(collection_info, 'vectors_count', None)
            points_count = getattr(collection_info, 'points_count', None)
            if vectors_count is None and points_count is None:
                # Newer qdrant-client versions use different attribute names
                vectors_count = getattr(collection_info, 'indexed_vectors_count', 0)
                points_count = getattr(collection_info, 'points_count', 0)
                # Try to get from collection info dict
                if hasattr(collection_info, 'dict'):
                    info_dict = collection_info.dict() if callable(getattr(collection_info, 'dict', None)) else {}
                    vectors_count = info_dict.get('vectors_count', vectors_count)
                    points_count = info_dict.get('points_count', points_count)
            return {
                'available': True,
                'name': collection_name,
                'vectors_count': vectors_count or 0,
                'points_count': points_count or 0,
                'status': str(getattr(collection_info, 'status', 'unknown'))
            }
        except Exception as e:
            logger.error(f"Failed to get regulation collection stats: {e}", exc_info=True)
            return {'available': False, 'error': str(e)}

    async def search_similar_clauses(
        self,
        query_text: str,
        organization: str,
        limit: int = 10,
        score_threshold: float = 0.25,
        policy_id: Optional[str] = None
    ) -> List[Dict]:
        """
        Search for similar clauses using semantic similarity.

        Args:
            query_text: Search query text
            organization: Organization filter
            limit: Maximum number of results
            score_threshold: Minimum similarity score (0-1)
            policy_id: Optional policy ID filter

        Returns:
            List of similar clauses with scores
        """
        if not self.qdrant_client:
            logger.warning("Qdrant client not available - returning empty results")
            return []

        try:
            # Generate embedding for query
            query_embedding = await self.llm_service.generate_embeddings(query_text)

            # Ensure embedding has correct dimension
            if len(query_embedding) != self.vector_size:
                if len(query_embedding) < self.vector_size:
                    query_embedding = query_embedding + [0.0] * (self.vector_size - len(query_embedding))
                else:
                    query_embedding = query_embedding[:self.vector_size]

            # Build filter conditions
            filter_conditions = []
            if organization:  # Only filter by org if provided and non-empty
                filter_conditions.append(
                    FieldCondition(
                        key="organization",
                        match=MatchValue(value=organization)
                    )
                )

            if policy_id:
                filter_conditions.append(
                    FieldCondition(
                        key="policy_id",
                        match=MatchValue(value=policy_id)
                    )
                )

            # Search in Qdrant (using query_points for qdrant-client >= 1.16)
            query_response = self.qdrant_client.query_points(
                collection_name=self.collection_name,
                query=query_embedding,
                query_filter=Filter(must=filter_conditions) if filter_conditions else None,
                limit=limit,
                score_threshold=score_threshold
            )
            search_results = query_response.points if hasattr(query_response, 'points') else []

            # Format results
            results = []
            for result in search_results:
                results.append({
                    'clause_id': result.payload.get('clause_id'),
                    'policy_id': result.payload.get('policy_id'),
                    'text': result.payload.get('text'),
                    'section': result.payload.get('section'),
                    'title': result.payload.get('title'),
                    'score': result.score,
                    'requirement_type': result.payload.get('requirement_type'),
                    'criticality': result.payload.get('criticality'),
                    'tags': result.payload.get('tags', [])
                })

            logger.info(f"Found {len(results)} similar clauses for query")
            return results

        except Exception as e:
            logger.error(f"Failed to search similar clauses: {e}", exc_info=True)
            return []

    async def delete_policy_clauses(self, policy_id: str) -> bool:
        """
        Delete all clause embeddings for a specific policy.

        Args:
            policy_id: Policy identifier

        Returns:
            True if successful, False otherwise
        """
        if not self.qdrant_client:
            return False

        try:
            # Delete points by filter
            self.qdrant_client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="policy_id",
                            match=MatchValue(value=policy_id)
                        )
                    ]
                )
            )
            logger.info(f"Deleted clause embeddings for policy {policy_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete policy clauses from Qdrant: {e}", exc_info=True)
            return False

    async def get_collection_stats(self) -> Dict:
        """
        Get statistics about the vector collection.

        Returns:
            Dictionary with collection statistics
        """
        if not self.qdrant_client:
            return {'available': False, 'error': 'Qdrant client not available'}

        try:
            collection_info = self.qdrant_client.get_collection(self.collection_name)
            vectors_count = getattr(collection_info, 'vectors_count', None)
            points_count = getattr(collection_info, 'points_count', None)
            if vectors_count is None and points_count is None:
                vectors_count = getattr(collection_info, 'indexed_vectors_count', 0)
                points_count = 0
                if hasattr(collection_info, 'dict'):
                    info_dict = collection_info.dict() if callable(getattr(collection_info, 'dict', None)) else {}
                    vectors_count = info_dict.get('vectors_count', vectors_count)
                    points_count = info_dict.get('points_count', points_count)
            return {
                'available': True,
                'name': self.collection_name,
                'vectors_count': vectors_count or 0,
                'points_count': points_count or 0,
                'status': str(getattr(collection_info, 'status', 'unknown'))
            }
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}", exc_info=True)
            return {'available': False, 'error': str(e)}
