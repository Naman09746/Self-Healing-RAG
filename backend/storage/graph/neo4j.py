from neo4j import GraphDatabase
from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger(__name__)

class GraphStore:
    def __init__(self):
        self.uri = "bolt://localhost:7687"
        self.user = "neo4j"
        self.password = "password"
        self._driver = None
        self.connect()
        
    def connect(self):
        try:
            self._driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            self._driver.verify_connectivity()
            logger.info("Connected to Neo4j successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {str(e)}")
            self._driver = None

    def close(self):
        if self._driver:
            self._driver.close()

    def add_entity(self, name: str, entity_type: str, properties: dict = None):
        if not self._driver:
            return
        
        with self._driver.session() as session:
            session.execute_write(self._add_entity_node, name, entity_type, properties)

    def add_relationship(self, source_name: str, target_name: str, rel_type: str, properties: dict = None):
        if not self._driver:
            return
            
        with self._driver.session() as session:
            session.execute_write(self._add_relationship_edge, source_name, target_name, rel_type, properties)

    def query_graph(self, cypher_query: str, parameters: dict = None):
        if not self._driver:
            return []
            
        with self._driver.session() as session:
            result = session.run(cypher_query, parameters)
            return [record.data() for record in result]

    @staticmethod
    def _add_entity_node(tx, name, entity_type, properties):
        props = properties or {}
        query = (
            f"MERGE (n:{entity_type} {{name: $name}}) "
            "SET n += $props "
            "RETURN n"
        )
        tx.run(query, name=name, props=props)

    @staticmethod
    def _add_relationship_edge(tx, source_name, target_name, rel_type, properties):
        props = properties or {}
        query = (
            "MATCH (a {name: $source_name}) "
            "MATCH (b {name: $target_name}) "
            f"MERGE (a)-[r:{rel_type}]->(b) "
            "SET r += $props "
            "RETURN r"
        )
        tx.run(query, source_name=source_name, target_name=target_name, props=props)

graph_store = GraphStore()
