import time
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import ingestion, retrieval, feedback, agent


from app.config import settings
from app.core.neo4j import Neo4jClient
from app.dependencies import get_neo4j_repository


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        repository = get_neo4j_repository()
        repository.ensure_schema()
        
        # Wait for the vector index to become ONLINE before starting the app
        print(f"Waiting for vector index '{repository.vector_index_name}' to become ONLINE...")
        with repository.driver.session(database=repository.database) as session:
            for i in range(30):  # Wait up to 30 seconds
                result = session.run(
                    "SHOW INDEXES YIELD name, state WHERE name = $name RETURN state",
                    name=repository.vector_index_name
                ).single()
                
                if result and result["state"] == "ONLINE":
                    print(f"✅ Vector index '{repository.vector_index_name}' is ONLINE and ready for search!")
                    break
                
                time.sleep(1)
            else:
                print("⚠️ Warning: Vector index did not reach ONLINE state within 30 seconds. Retrieval might fail.")
                
    except Exception as exc:
        print(f"WARNING: Neo4j schema initialization failed: {exc}")

    yield

    Neo4jClient.close()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)



app.include_router(ingestion.router)
app.include_router(retrieval.router)
app.include_router(feedback.router)
app.include_router(agent.router)

@app.get("/health")
def health():
    return {"status": "ok"}