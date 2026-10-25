# check_indexes.py
from neo4j import GraphDatabase

driver = GraphDatabase.driver(
    "bolt://100.53.45.88:7687",
    auth=("neo4j", "sir-alcoholism-pens")
)

with driver.session(database="neo4j") as session:
    result = session.run("""
        SHOW INDEXES 
        YIELD name, state, type, populationPercent 
        WHERE type = 'VECTOR'
        RETURN name, state, type, populationPercent
    """)
    
    print("--- Current Vector Indexes ---")
    for record in result:
        print(f"Index: {record['name']} | State: {record['state']} | Populating: {record['populationPercent']}%")
        
driver.close()