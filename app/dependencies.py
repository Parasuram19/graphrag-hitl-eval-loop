from functools import lru_cache

from app.config import settings
from app.controllers.ingestion_controller import IngestionController
from app.controllers.retrieval_controller import RetrievalController
from app.core.neo4j import Neo4jClient
from app.repositories.neo4j_repository import Neo4jRepository
from app.services.chunking_service import ChunkingService
from app.services.embedding_service import EmbeddingService
from app.services.graph_extraction_service import GraphExtractionService
from app.services.ingestion_service import IngestionService
from app.services.retrieval_service import RetrievalService
from app.services.rrf_service import RRFService
from app.services.feedback_service import FeedbackService
from app.controllers.feedback_controller import FeedbackController
from app.services.agent_service import AgentService
from app.controllers.agent_controller import AgentController
from app.agents.graphrag_agent import build_graphrag_agent




@lru_cache
def get_neo4j_repository() -> Neo4jRepository:
    return Neo4jRepository(
        driver=Neo4jClient.get_driver(),
        database=settings.neo4j_database,
        vector_index_name=settings.vector_index_name,
        embedding_dimension=settings.embedding_dimension,
    )


@lru_cache
def get_chunking_service() -> ChunkingService:
    return ChunkingService(settings)


@lru_cache
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService(settings)


@lru_cache
def get_graph_extraction_service() -> GraphExtractionService:
    return GraphExtractionService()


@lru_cache
def get_rrf_service() -> RRFService:
    return RRFService()


@lru_cache
def get_ingestion_service() -> IngestionService:
    return IngestionService(
        repository=get_neo4j_repository(),
        chunking_service=get_chunking_service(),
        embedding_service=get_embedding_service(),
        graph_extraction_service=get_graph_extraction_service(),
        settings=settings,
    )


@lru_cache
def get_retrieval_service() -> RetrievalService:
    return RetrievalService(
        repository=get_neo4j_repository(),
        embedding_service=get_embedding_service(),
        rrf_service=get_rrf_service(),
        settings=settings,
    )


@lru_cache
def get_ingestion_controller() -> IngestionController:
    return IngestionController(get_ingestion_service())


@lru_cache
def get_retrieval_controller() -> RetrievalController:
    return RetrievalController(get_retrieval_service())



@lru_cache
def get_feedback_service() -> FeedbackService:
    return FeedbackService(repository=get_neo4j_repository())


@lru_cache
def get_feedback_controller() -> FeedbackController:
    return FeedbackController(get_feedback_service())

@lru_cache
def get_agent_service() -> AgentService:
    retrieval_service = get_retrieval_service()
    feedback_service = get_feedback_service()
    agent = build_graphrag_agent(retrieval_service, feedback_service)
    return AgentService(agent)


@lru_cache
def get_agent_controller() -> AgentController:
    return AgentController(
        agent_service=get_agent_service(),
        feedback_controller=get_feedback_controller(),
    )