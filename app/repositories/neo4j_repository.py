import re
from collections import defaultdict
from typing import Any, Dict, List, Optional


class Neo4jRepository:
    def __init__(
        self,
        driver,
        database: str,
        vector_index_name: str,
        embedding_dimension: int,
    ):
        self.driver = driver
        self.database = database
        self.vector_index_name = self._sanitize_identifier(vector_index_name)
        self.embedding_dimension = int(embedding_dimension)

    @staticmethod
    def _sanitize_identifier(value: str) -> str:
        value = re.sub(r"[^A-Za-z0-9_]+", "_", value or "")
        return value or "chunk_embedding"

    @staticmethod
    def _sanitize_relationship_type(value: str) -> Optional[str]:
        value = re.sub(r"[^A-Za-z0-9_]+", "_", (value or "").upper())
        value = re.sub(r"_+", "_", value).strip("_")

        if not value or not re.fullmatch(r"[A-Z][A-Z0-9_]*", value):
            return None

        return value

    def ensure_schema(self) -> None:
        constraint_queries = [
            "CREATE CONSTRAINT document_id_unique IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
            "CREATE CONSTRAINT chunk_id_unique IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT entity_name_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.name IS UNIQUE",
            "CREATE CONSTRAINT role_name_unique IF NOT EXISTS FOR (r:Role) REQUIRE r.name IS UNIQUE",
        ]

        with self.driver.session(database=self.database) as session:
            # 1. Create constraints
            for query in constraint_queries:
                session.run(query).consume()

            # 2. Check if vector index exists and has correct dimensions
            result = session.run(
                "SHOW INDEXES YIELD name, type, options WHERE name = $name AND type = 'VECTOR' RETURN options",
                name=self.vector_index_name
            ).single()

            needs_creation = True
            if result:
                options = result["options"] or {}
                index_config = options.get("indexConfig", {})
                current_dims = index_config.get("vector.dimensions")
                
                if current_dims == self.embedding_dimension:
                    print(f"✅ Vector index '{self.vector_index_name}' already exists with correct dimensions ({current_dims}).")
                    needs_creation = False
                else:
                    print(f"⚠️ Vector index '{self.vector_index_name}' exists but has {current_dims} dimensions (expected {self.embedding_dimension}). Dropping and recreating...")
                    session.run(f"DROP INDEX {self.vector_index_name}").consume()

            # 3. Create index if needed
            if needs_creation:
                vector_query = f"""
                CREATE VECTOR INDEX {self.vector_index_name} 
                FOR (c:Chunk) ON (c.embedding)
                OPTIONS {{indexConfig: {{`vector.dimensions`: {self.embedding_dimension}, `vector.similarity_function`: 'cosine'}}}}
                """
                print(f"Creating vector index '{self.vector_index_name}' with {self.embedding_dimension} dimensions...")
                session.run(vector_query).consume()

    def save_document(
        self,
        *,
        document_id: str,
        title: str,
        metadata_json: str,
        allowed_roles: List[str],
        chunks: List[Dict[str, Any]],
        entities: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        def _tx(tx):
            tx.run(
                """
                MATCH (d:Document {id: $document_id})
                OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:Chunk)
                DETACH DELETE c
                """,
                document_id=document_id,
            )

            tx.run(
                """
                MATCH (d:Document {id: $document_id})
                OPTIONAL MATCH (d)-[m:MENTIONS]->()
                DELETE m
                """,
                document_id=document_id,
            )

            tx.run(
                """
                MATCH (d:Document {id: $document_id})
                OPTIONAL MATCH (:Role)-[access:CAN_ACCESS]->(d)
                DELETE access
                """,
                document_id=document_id,
            )

            tx.run(
                """
                MERGE (d:Document {id: $document_id})
                SET d.title = $title,
                    d.metadata = $metadata_json,
                    d.public = $public,
                    d.updated_at = datetime(),
                    d.created_at = coalesce(d.created_at, datetime())
                """,
                document_id=document_id,
                title=title,
                metadata_json=metadata_json,
                public=len(allowed_roles) == 0,
            )

            if allowed_roles:
                tx.run(
                    """
                    UNWIND $roles AS role_name
                    MERGE (r:Role {name: role_name})
                    WITH r
                    MATCH (d:Document {id: $document_id})
                    MERGE (r)-[:CAN_ACCESS]->(d)
                    """,
                    roles=allowed_roles,
                    document_id=document_id,
                )

            if chunks:
                tx.run(
                    """
                    UNWIND $chunks AS chunk
                    MATCH (d:Document {id: $document_id})
                    MERGE (c:Chunk {id: chunk.id})
                    SET c.content = chunk.content,
                        c.chunk_index = chunk.index,
                        c.embedding = chunk.embedding,
                        c.document_id = $document_id,
                        c.updated_at = datetime()
                    MERGE (d)-[:HAS_CHUNK]->(c)
                    """,
                    chunks=chunks,
                    document_id=document_id,
                )

            if entities:
                tx.run(
                    """
                    UNWIND $entities AS entity
                    MERGE (e:Entity {name: entity.name})
                    SET e.kind = coalesce(entity.kind, e.kind),
                        e.updated_at = datetime()
                    WITH e, entity
                    MATCH (d:Document {id: $document_id})
                    MERGE (d)-[:MENTIONS]->(e)
                    WITH e, entity
                    UNWIND entity.chunk_ids AS chunk_id
                    MATCH (c:Chunk {id: chunk_id})
                    MERGE (c)-[:MENTIONS]->(e)
                    """,
                    entities=entities,
                    document_id=document_id,
                )

            grouped_relationships = defaultdict(list)

            for relationship in relationships:
                rel_type = self._sanitize_relationship_type(
                    relationship.get("type", "")
                )
                source = relationship.get("source")
                target = relationship.get("target")

                if rel_type and source and target:
                    grouped_relationships[rel_type].append(
                        {
                            "source": source,
                            "target": target,
                        }
                    )

            for rel_type, pairs in grouped_relationships.items():
                tx.run(
                    f"""
                    UNWIND $pairs AS pair
                    MATCH (a:Entity {{name: pair.source}})
                    MATCH (b:Entity {{name: pair.target}})
                    MERGE (a)-[:{rel_type}]->(b)
                    """,
                    pairs=pairs,
                )

            result = tx.run(
                """
                MATCH (d:Document {id: $document_id})
                OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:Chunk)
                OPTIONAL MATCH (d)-[:MENTIONS]->(e:Entity)
                RETURN count(DISTINCT c) AS chunks_saved,
                       count(DISTINCT e) AS entities_saved
                """,
                document_id=document_id,
            ).single()

            return {
                "chunks_saved": result["chunks_saved"],
                "entities_saved": result["entities_saved"],
            }

                # NEW (Correct):
        with self.driver.session(database=self.database) as session:
            return session.execute_write(_tx)

    def vector_search(
        self,
        embedding: List[float],
        limit: int,
        user_roles: List[str] = None,
    ) -> List[Dict[str, Any]]:
        
        # If no roles provided, only return public documents
        if user_roles is None:
            user_roles = []

        query = f"""
        CALL db.index.vector.queryNodes('{self.vector_index_name}', $limit, $embedding)
        YIELD node AS chunk, score
        OPTIONAL MATCH (d:Document {{id: chunk.document_id}})
        WHERE d.public = true
           OR EXISTS {{
                MATCH (r:Role)-[:CAN_ACCESS]->(d)
                WHERE r.name IN $user_roles
           }}
        RETURN chunk.id AS chunk_id,
               chunk.content AS content,
               d.title AS document_title,
               score AS score
        ORDER BY score DESC
        """

        with self.driver.session(database=self.database) as session:
            result = session.run(
                query,
                limit=limit,
                embedding=embedding,
                user_roles=user_roles,
            )
            return [record.data() for record in result]

    def graph_search(
        self,
        terms: List[str],
        limit: int,
        user_roles: List[str] = None,
    ) -> List[Dict[str, Any]]:
        if not terms:
            return []

        if user_roles is None:
            user_roles = []

        query = """
        UNWIND $terms AS term
        MATCH (e:Entity)
        WHERE toLower(e.name) CONTAINS toLower(term)
        MATCH (e)<-[:MENTIONS]-(c:Chunk)
        OPTIONAL MATCH (d:Document {id: c.document_id})
        WHERE d.public = true
           OR EXISTS {
                MATCH (r:Role)-[:CAN_ACCESS]->(d)
                WHERE r.name IN $user_roles
           }
        WITH c, d, e, count(DISTINCT term) AS term_matches
        WITH c,
             d,
             collect(DISTINCT e.name) AS matched_entities,
             sum(term_matches) AS score
        RETURN c.id AS chunk_id,
               c.content AS content,
               d.title AS document_title,
               score AS score,
               matched_entities AS matched_entities
        ORDER BY score DESC
        LIMIT $limit
        """

        with self.driver.session(database=self.database) as session:
            result = session.run(
                query,
                terms=terms,
                limit=limit,
                user_roles=user_roles,
            )
            return [record.data() for record in result]

    def store_feedback(
        self,
        *,
        query: str,
        generated_answer: str,
        feedback_type: str,
        rating: int,
        comment: str,
        correction: str,
        chunk_ids: List[str],
        entity_names: List[str],
        document_titles: List[str],
        user_id: str,
    ) -> Dict[str, Any]:
        
        def _tx(tx):
            # 1. Create Feedback node
            result = tx.run(
                """
                CREATE (f:Feedback {
                    id: randomUUID(),
                    query: $query,
                    generated_answer: $generated_answer,
                    feedback_type: $feedback_type,
                    rating: $rating,
                    comment: $comment,
                    correction: $correction,
                    created_at: datetime()
                })
                RETURN f.id AS feedback_id
                """,
                query=query,
                generated_answer=generated_answer,
                feedback_type=feedback_type,
                rating=rating,
                comment=comment or "",
                correction=correction or "",
            ).single()

            feedback_id = result["feedback_id"]

            # 2. Link to User
            if user_id:
                tx.run(
                    """
                    MERGE (u:User {id: $user_id})
                    WITH u
                    MATCH (f:Feedback {id: $feedback_id})
                    MERGE (u)-[:GAVE_FEEDBACK]->(f)
                    """,
                    user_id=user_id,
                    feedback_id=feedback_id,
                )

            # 3. Link to Chunks
            if chunk_ids:
                tx.run(
                    """
                    UNWIND $chunk_ids AS cid
                    MATCH (c:Chunk {id: cid})
                    WITH c
                    MATCH (f:Feedback {id: $feedback_id})
                    MERGE (f)-[:ABOUT_CHUNK]->(c)
                    """,
                    chunk_ids=chunk_ids,
                    feedback_id=feedback_id,
                )

            # 4. Link to Entities
            if entity_names:
                tx.run(
                    """
                    UNWIND $entity_names AS ename
                    MATCH (e:Entity {name: ename})
                    WITH e
                    MATCH (f:Feedback {id: $feedback_id})
                    MERGE (f)-[:ABOUT_ENTITY]->(e)
                    """,
                    entity_names=entity_names,
                    feedback_id=feedback_id,
                )

            # 5. Link to Documents
            if document_titles:
                tx.run(
                    """
                    UNWIND $document_titles AS dtitle
                    MATCH (d:Document {title: dtitle})
                    WITH d
                    MATCH (f:Feedback {id: $feedback_id})
                    MERGE (f)-[:ABOUT_DOCUMENT]->(d)
                    """,
                    document_titles=document_titles,
                    feedback_id=feedback_id,
                )

            return {
                "feedback_id": feedback_id,
                "linked_chunks": len(chunk_ids),
                "linked_entities": len(entity_names),
                "linked_documents": len(document_titles),
            }

        return self.driver.execute_write(_tx)

    def get_feedback_for_entity(self, entity_name: str) -> List[Dict[str, Any]]:
        """Get all feedback linked to a specific entity."""
        query = """
        MATCH (f:Feedback)-[:ABOUT_ENTITY]->(e:Entity {name: $entity_name})
        RETURN f.id, f.feedback_type, f.rating, f.comment, f.created_at
        ORDER BY f.created_at DESC
        """
        with self.driver.session(database=self.database) as session:
            result = session.run(query, entity_name=entity_name)
            return [record.data() for record in result]

    def get_negative_feedback_summary(self) -> List[Dict[str, Any]]:
        """Get summary of negative feedback grouped by entity."""
        query = """
        MATCH (f:Feedback)-[:ABOUT_ENTITY]->(e:Entity)
        WHERE f.rating = -1
        RETURN e.name AS entity_name,
               count(f) AS negative_count,
               collect(f.feedback_type) AS feedback_types
        ORDER BY negative_count DESC
        """
        with self.driver.session(database=self.database) as session:
            result = session.run(query)
            return [record.data() for record in result]

    def save_interaction(
        self,
        *,
        interaction_id: str,
        query: str,
        answer: str,
        user_id: str,
        chunk_ids: List[str],
        entity_names: List[str],
        document_titles: List[str],
    ) -> None:
        """Saves the agent's interaction context to the graph."""
        def _tx(tx):
            tx.run(
                """
                CREATE (i:Interaction {
                    id: $interaction_id,
                    query: $user_query,
                    answer: $answer,
                    created_at: datetime()
                })
                """,
                interaction_id=interaction_id, 
                user_query=query,  # FIX: Renamed from query=query to user_query=query
                answer=answer,
            )

            if user_id:
                tx.run(
                    """
                    MERGE (u:User {id: $user_id})
                    WITH u
                    MATCH (i:Interaction {id: $interaction_id})
                    MERGE (u)-[:MADE_INTERACTION]->(i)
                    """,
                    user_id=user_id, interaction_id=interaction_id,
                )

            if chunk_ids:
                tx.run(
                    """
                    UNWIND $chunk_ids AS cid
                    MATCH (c:Chunk {id: cid})
                    WITH c
                    MATCH (i:Interaction {id: $interaction_id})
                    MERGE (i)-[:RETRIEVED]->(c)
                    """,
                    chunk_ids=chunk_ids, interaction_id=interaction_id,
                )

            if entity_names:
                tx.run(
                    """
                    UNWIND $entity_names AS ename
                    MATCH (e:Entity {name: ename})
                    WITH e
                    MATCH (i:Interaction {id: $interaction_id})
                    MERGE (i)-[:IDENTIFIED]->(e)
                    """,
                    entity_names=entity_names, interaction_id=interaction_id,
                )

            if document_titles:
                tx.run(
                    """
                    UNWIND $dtitles AS dtitle
                    MATCH (d:Document {title: dtitle})
                    WITH d
                    MATCH (i:Interaction {id: $interaction_id})
                    MERGE (i)-[:CITED]->(d)
                    """,
                    dtitles=document_titles, interaction_id=interaction_id,
                )

        with self.driver.session(database=self.database) as session:
            session.execute_write(_tx)

    def store_feedback_by_interaction(
        self,
        *,
        interaction_id: str,
        feedback_type: str,
        rating: int,
        comment: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """Creates feedback and auto-links it to the interaction's context."""
        def _tx(tx):
            result = tx.run(
                """
                MATCH (i:Interaction {id: $interaction_id})
                CREATE (f:Feedback {
                    id: randomUUID(),
                    feedback_type: $feedback_type,
                    rating: $rating,
                    comment: $comment,
                    created_at: datetime()
                })
                CREATE (f)-[:EVALUATES]->(i)
                
                WITH i, f
                OPTIONAL MATCH (i)-[:RETRIEVED]->(c:Chunk)
                FOREACH (x IN CASE WHEN c IS NOT NULL THEN [1] ELSE [] END | CREATE (f)-[:ABOUT_CHUNK]->(c))
                
                WITH i, f
                OPTIONAL MATCH (i)-[:IDENTIFIED]->(e:Entity)
                FOREACH (x IN CASE WHEN e IS NOT NULL THEN [1] ELSE [] END | CREATE (f)-[:ABOUT_ENTITY]->(e))
                
                WITH i, f
                OPTIONAL MATCH (i)-[:CITED]->(d:Document)
                FOREACH (x IN CASE WHEN d IS NOT NULL THEN [1] ELSE [] END | CREATE (f)-[:ABOUT_DOCUMENT]->(d))
                
                RETURN f.id AS feedback_id
                """,
                interaction_id=interaction_id,
                feedback_type=feedback_type,
                rating=rating,
                comment=comment or "",
            ).single()

            # FIX: Check if result is None (meaning the Interaction wasn't found)
            if result is None:
                raise ValueError(f"Interaction ID '{interaction_id}' not found in database. The agent may not have saved it successfully.")

            feedback_id = result["feedback_id"]

            if user_id:
                tx.run(
                    """
                    MERGE (u:User {id: $user_id})
                    WITH u
                    MATCH (f:Feedback {id: $feedback_id})
                    MERGE (u)-[:GAVE_FEEDBACK]->(f)
                    """,
                    user_id=user_id,
                    feedback_id=feedback_id,
                )

            return {"feedback_id": feedback_id, "status": "stored"}

        with self.driver.session(database=self.database) as session:
            return session.execute_write(_tx)