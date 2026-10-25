# fix_index.py
from neo4j import GraphDatabase
import time

print("Connecting to Neo4j Sandbox...")
driver = GraphDatabase.driver(
    "bolt://100.53.45.88:7687",
    auth=("neo4j", "sir-alcoholism-pens")
)

try:
    with driver.session(database="neo4j") as session:
        print("1. Dropping old/broken indexes...")
        session.run("DROP INDEX chunk_embedding IF EXISTS").consume()
        session.run("DROP INDEX chunk_embedding_384 IF EXISTS").consume()
        
        print("2. Creating new 384-dimension vector index...")
        create_query = """
        CREATE VECTOR INDEX chunk_embedding_384 
        FOR (c:Chunk) ON (c.embedding)
        OPTIONS {indexConfig: {`vector.dimensions`: 384, `vector.similarity_function`: 'cosine'}}
        """
        session.run(create_query).consume()
        
        print("3. Waiting for index to populate and become ONLINE...")
        for i in range(30):
            result = session.run("""
                SHOW INDEXES 
                YIELD name, state, populationPercent 
                WHERE name = 'chunk_embedding_384' 
                RETURN state, populationPercent
            """).single()
            
            if result:
                state = result["state"]
                pop = result["populationPercent"]
                print(f"   Attempt {i+1}: State={state}, Populating={pop}%")
                if state == "ONLINE":
                    print("✅ SUCCESS! Index is ONLINE and ready for search!")
                    break
            time.sleep(2)
        else:
            print("⚠️ Warning: Index did not become ONLINE within 60 seconds.")
            
        print("\n--- Final State of All Indexes ---")
        result = session.run("SHOW INDEXES YIELD name, state, type")
        for r in result:
            print(f"  {r['name']} | {r['type']} | {r['state']}")

except Exception as e:
    print(f"❌ ERROR: {e}")
finally:
    driver.close()