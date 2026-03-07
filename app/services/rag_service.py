from typing import List, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from openai import AsyncOpenAI
import logging

from app.config import settings
from app.db.models import KnowledgeBase


logger = logging.getLogger(__name__)


class RAGService:
    """RAG service using pgvector for semantic search."""

    def __init__(self):
        # Use OpenRouter for embeddings
        self.client = AsyncOpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url
        )
        self.embedding_model = settings.openrouter_embedding_model
        self.top_k = settings.rag_top_k
        self.similarity_threshold = settings.rag_similarity_threshold

    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text using OpenRouter.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        try:
            response = await self.client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise

    async def search_knowledge_base(
        self,
        query: str,
        session: AsyncSession,
        source_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        category: Optional[str] = None
    ) -> List[Dict]:
        """
        Search knowledge base semantically using pgvector.

        Args:
            query: Search query
            session: Database session
            source_type: Filter by source type
            tags: Filter by tags
            category: Filter by category

        Returns:
            List of relevant knowledge items
        """
        try:
            # Generate embedding for query
            query_embedding = await self.generate_embedding(query)

            # Build SQL query with pgvector
            sql = """
                SELECT
                    id, title, content, source_type, tags, category,
                    1 - (embedding <=> :embedding) as similarity
                FROM knowledge_base
                WHERE embedding IS NOT NULL
            """

            params = {"embedding": query_embedding}

            # Add filters
            if source_type:
                sql += " AND source_type = :source_type"
                params["source_type"] = source_type

            if category:
                sql += " AND category = :category"
                params["category"] = category

            sql += f"""
                AND 1 - (embedding <=> :embedding) >= :threshold
                ORDER BY embedding <=> :embedding
                LIMIT :limit
            """
            params["threshold"] = self.similarity_threshold
            params["limit"] = self.top_k

            result = await session.execute(text(sql), params)
            rows = result.fetchall()

            knowledge_items = []
            for row in rows:
                knowledge_items.append({
                    "id": str(row[0]),
                    "title": row[1],
                    "content": row[2],
                    "source_type": row[3],
                    "tags": row[4],
                    "category": row[5],
                    "similarity": float(row[6])
                })

            logger.info(f"Found {len(knowledge_items)} knowledge items for query: {query[:50]}...")
            return knowledge_items

        except Exception as e:
            logger.error(f"Error searching knowledge base: {e}")
            return []

    async def add_knowledge(
        self,
        title: str,
        content: str,
        source_type: str,
        session: AsyncSession,
        tags: Optional[List[str]] = None,
        category: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> KnowledgeBase:
        """
        Add new knowledge to the knowledge base.

        Args:
            title: Knowledge title
            content: Knowledge content
            source_type: Type of source (faq, script, doc, response)
            session: Database session
            tags: Optional tags
            category: Optional category
            metadata: Optional metadata

        Returns:
            Created knowledge item
        """
        try:
            # Generate embedding
            embedding = await self.generate_embedding(content)

            # Create knowledge item
            knowledge = KnowledgeBase(
                title=title,
                content=content,
                source_type=source_type,
                tags=tags or [],
                category=category,
                embedding=embedding,
                metadata=metadata or {}
            )

            session.add(knowledge)
            await session.commit()
            await session.refresh(knowledge)

            logger.info(f"Added knowledge: {title}")
            return knowledge

        except Exception as e:
            logger.error(f"Error adding knowledge: {e}")
            await session.rollback()
            raise

    async def format_context(self, knowledge_items: List[Dict]) -> str:
        """
        Format knowledge items into context for LLM.

        Args:
            knowledge_items: List of knowledge items

        Returns:
            Formatted context string
        """
        if not knowledge_items:
            return ""

        context_parts = []
        for item in knowledge_items:
            part = f"""
Fonte: {item['title']} ({item['source_type']})
{item['content']}
"""
            context_parts.append(part)

        return "\n".join(context_parts)


# Singleton instance
rag_service = RAGService()
