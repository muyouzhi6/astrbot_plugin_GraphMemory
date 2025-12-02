import json
import time

from astrbot.api import logger

from .graph_engine import GraphEngine


class GraphService:
    def __init__(self, engine: GraphEngine):
        self.engine = engine

    def get_all_nodes(
        self,
        session_id: str | None = None,
        persona_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """[Sync] 获取节点列表（分页）"""
        filter_sql = []
        params = {}
        params["limit"] = limit
        params["offset"] = offset

        if session_id:
            filter_sql.append("n.session_id = $sid")
            params["sid"] = session_id
        if persona_id:
            filter_sql.append("n.persona_id = $pid")
            params["pid"] = persona_id

        where_clause = " AND ".join(filter_sql) if filter_sql else "true"

        query = f"""
            MATCH (n:Entity)
            WHERE {where_clause}
            RETURN n.id, n.name, n.type, n.attributes, n.session_id, n.persona_id, n.importance, n.updated_at
            SKIP $offset LIMIT $limit
        """

        try:
            res = self.engine.execute_query(query, params)
            nodes = []
            while res.has_next():
                row = res.get_next()
                nodes.append(
                    {
                        "id": row[0],
                        "name": row[1],
                        "type": row[2],
                        "attributes": json.loads(row[3] or "{}"),
                        "session_id": row[4],
                        "persona_id": row[5],
                        "importance": row[6],
                        "updated_at": row[7],
                    }
                )
            return nodes
        except Exception as e:
            logger.error(f"[GraphService] get_all_nodes failed: {e}")
            return []

    def get_node_details(self, node_id: str) -> dict | None:
        """[Sync] 获取单个节点详情"""
        query = "MATCH (n:Entity) WHERE n.id = $id RETURN n.id, n.name, n.type, n.attributes, n.session_id, n.persona_id, n.importance, n.updated_at"
        try:
            res = self.engine.execute_query(query, {"id": node_id})
            if res.has_next():
                row = res.get_next()
                return {
                    "id": row[0],
                    "name": row[1],
                    "type": row[2],
                    "attributes": json.loads(row[3] or "{}"),
                    "session_id": row[4],
                    "persona_id": row[5],
                    "importance": row[6],
                    "updated_at": row[7],
                }
            return None
        except Exception as e:
            logger.error(f"[GraphService] get_node_details failed: {e}")
            return None

    async def debug_search(
        self, keywords: list[str], session_id: str, persona_id: str
    ) -> dict:
        """[Async] 调试搜索，返回结构化子图"""
        return await self.engine.search_subgraph_structure(
            keywords, session_id, persona_id, hops=2
        )

    def search_nodes(
        self, keyword: str, session_id: str | None = None, persona_id: str | None = None
    ) -> list[dict]:
        """[Sync] 模糊搜索节点"""
        filter_sql = ["n.name CONTAINS $kw"]
        params = {"kw": keyword}
        if session_id:
            filter_sql.append("n.session_id = $sid")
            params["sid"] = session_id
        if persona_id:
            filter_sql.append("n.persona_id = $pid")
            params["pid"] = persona_id

        where_clause = " AND ".join(filter_sql)

        query = f"""
            MATCH (n:Entity)
            WHERE {where_clause}
            RETURN n.id, n.name, n.type, n.session_id, n.persona_id
            LIMIT 50
        """
        try:
            res = self.engine.execute_query(query, params)
            nodes = []
            while res.has_next():
                row = res.get_next()
                nodes.append(
                    {
                        "id": row[0],
                        "name": row[1],
                        "type": row[2],
                        "session_id": row[3],
                        "persona_id": row[4],
                    }
                )
            return nodes
        except Exception as e:
            logger.error(f"[GraphService] search_nodes failed: {e}")
            return []

    def get_neighbors(self, node_id: str) -> dict:
        """[Sync] 获取节点的一跳邻居（包括入边和出边）"""
        # Outgoing
        out_query = """
            MATCH (a:Entity)-[r:Related]->(b:Entity)
            WHERE a.id = $id
            RETURN b.id, b.name, b.type, r.relation, r.weight, r.confidence
        """
        # Incoming
        in_query = """
            MATCH (a:Entity)-[r:Related]->(b:Entity)
            WHERE b.id = $id
            RETURN a.id, a.name, a.type, r.relation, r.weight, r.confidence
        """

        result = {"nodes": [], "edges": []}
        seen_nodes = {node_id}

        try:
            # Add self first
            self_node = self.get_node_details(node_id)
            if self_node:
                result["nodes"].append(
                    {
                        "id": self_node["id"],
                        "name": self_node["name"],
                        "type": self_node["type"],
                    }
                )

            # Outgoing
            res_out = self.engine.execute_query(out_query, {"id": node_id})
            while res_out.has_next():
                row = (
                    res_out.get_next()
                )  # b.id, b.name, b.type, r.rel, r.weight, r.conf
                if row[0] not in seen_nodes:
                    result["nodes"].append(
                        {"id": row[0], "name": row[1], "type": row[2]}
                    )
                    seen_nodes.add(row[0])
                result["edges"].append(
                    {
                        "source": node_id,
                        "target": row[0],
                        "relation": row[3],
                        "weight": row[4],
                        "confidence": row[5],
                    }
                )

            # Incoming
            res_in = self.engine.execute_query(in_query, {"id": node_id})
            while res_in.has_next():
                row = res_in.get_next()  # a.id, a.name, a.type, r.rel, r.weight, r.conf
                if row[0] not in seen_nodes:
                    result["nodes"].append(
                        {"id": row[0], "name": row[1], "type": row[2]}
                    )
                    seen_nodes.add(row[0])
                result["edges"].append(
                    {
                        "source": row[0],
                        "target": node_id,
                        "relation": row[3],
                        "weight": row[4],
                        "confidence": row[5],
                    }
                )

            return result
        except Exception as e:
            logger.error(f"[GraphService] get_neighbors failed: {e}")
            return {"nodes": [], "edges": []}

    def delete_node(self, node_id: str):
        """[Sync] 删除节点及其关联边"""
        query = "MATCH (n:Entity) WHERE n.id = $id DETACH DELETE n"
        try:
            self.engine.execute_query(query, {"id": node_id})
            logger.info(f"[GraphService] Deleted node {node_id}")
        except Exception as e:
            logger.error(f"[GraphService] delete_node failed: {e}")
            raise e

    def delete_edge(self, source_id: str, target_id: str, relation: str):
        """[Sync] 删除特定边"""
        query = """
            MATCH (a:Entity)-[r:Related]->(b:Entity)
            WHERE a.id = $src AND b.id = $tgt AND r.relation = $rel
            DELETE r
        """
        try:
            self.engine.execute_query(
                query, {"src": source_id, "tgt": target_id, "rel": relation}
            )
            logger.info(
                f"[GraphService] Deleted edge {source_id} --[{relation}]--> {target_id}"
            )
        except Exception as e:
            logger.error(f"[GraphService] delete_edge failed: {e}")
            raise e

    def update_node(
        self, node_id: str, name: str, type_: str, attributes: dict, importance: float
    ):
        """[Sync] 更新节点信息"""
        now = int(time.time())
        attr_str = json.dumps(attributes, ensure_ascii=False)
        query = """
            MATCH (n:Entity)
            WHERE n.id = $id
            SET n.name = $name, n.type = $type, n.attributes = $attr, n.importance = $imp, n.updated_at = $now
        """
        try:
            self.engine.execute_query(
                query,
                {
                    "id": node_id,
                    "name": name,
                    "type": type_,
                    "attr": attr_str,
                    "imp": importance,
                    "now": now,
                },
            )
        except Exception as e:
            logger.error(f"[GraphService] update_node failed: {e}")
            raise e

    def update_edge(
        self,
        source_id: str,
        target_id: str,
        old_relation: str,
        new_relation: str,
        weight: float,
    ):
        """[Sync] 更新边信息"""
        # 如果 relation 名字变了，需要 DELETE + CREATE
        if old_relation != new_relation:
            # 1. 获取旧边属性
            get_old = """
                MATCH (a:Entity)-[r:Related]->(b:Entity)
                WHERE a.id = $src AND b.id = $tgt AND r.relation = $old_rel
                RETURN r.confidence, r.source_user
            """
            conf = 1.0
            src_user = "unknown"
            try:
                res = self.engine.execute_query(
                    get_old,
                    {"src": source_id, "tgt": target_id, "old_rel": old_relation},
                )
                if res.has_next():
                    row = res.get_next()
                    conf = row[0]
                    src_user = row[1]
            except Exception:
                pass

            # 2. 删除旧边
            self.delete_edge(source_id, target_id, old_relation)

            # 3. 创建新边
            now = int(time.time())
            create_query = """
                MATCH (a:Entity {id: $src}), (b:Entity {id: $tgt})
                MERGE (a)-[r:Related {relation: $rel}]->(b)
                ON CREATE SET
                    r.weight = $weight, r.confidence = $conf, r.source_user = $user, r.updated_at = $now
                ON MATCH SET
                    r.weight = $weight, r.updated_at = $now
            """
            self.engine.execute_query(
                create_query,
                {
                    "src": source_id,
                    "tgt": target_id,
                    "rel": new_relation,
                    "weight": weight,
                    "conf": conf,
                    "user": src_user,
                    "now": now,
                },
            )

        else:
            # 仅更新属性
            now = int(time.time())
            query = """
                MATCH (a:Entity)-[r:Related]->(b:Entity)
                WHERE a.id = $src AND b.id = $tgt AND r.relation = $rel
                SET r.weight = $w, r.updated_at = $now
            """
            try:
                self.engine.execute_query(
                    query,
                    {
                        "src": source_id,
                        "tgt": target_id,
                        "rel": old_relation,
                        "w": weight,
                        "now": now,
                    },
                )
            except Exception as e:
                logger.error(f"[GraphService] update_edge failed: {e}")
                raise e

    def get_all_edges(
        self, session_id: str | None = None, persona_id: str | None = None
    ) -> list[dict]:
        """[Sync] 获取所有边"""
        filter_sql = []
        params = {}

        if session_id:
            filter_sql.append("a.session_id = $sid")
            params["sid"] = session_id
        if persona_id:
            filter_sql.append("a.persona_id = $pid")
            params["pid"] = persona_id

        where_clause = " AND ".join(filter_sql) if filter_sql else "true"

        query = f"""
            MATCH (a:Entity)-[r:Related]->(b:Entity)
            WHERE {where_clause}
            RETURN a.id, b.id, r.relation, r.weight, r.confidence
        """

        try:
            res = self.engine.execute_query(query, params)
            edges = []
            while res.has_next():
                row = res.get_next()
                edges.append(
                    {
                        "source": row[0],
                        "target": row[1],
                        "relation": row[2],
                        "weight": row[3],
                        "confidence": row[4],
                    }
                )
            return edges
        except Exception as e:
            logger.error(f"[GraphService] get_all_edges failed: {e}")
            return []
