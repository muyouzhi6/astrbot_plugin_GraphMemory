"""图谱数据接口"""


from fastapi import APIRouter, Depends, Query, Request

from ..schemas.common import ApiResponse
from ..utils.auth import verify_key

router = APIRouter()


@router.get("/session/{session_id}")
async def get_session_graph(
    request: Request,
    session_id: str,
    include_relations: bool = Query(True, description="是否包含关系"),
    max_entities: int = Query(100, description="最大实体数"),
    _: bool = Depends(verify_key),
):
    """获取会话图谱

    Args:
        session_id: 会话 ID
        include_relations: 是否包含关系
        max_entities: 最大实体数

    Returns:
        图谱数据（节点和边）
    """
    try:
        manager = request.app.state.manager
        await manager.ensure_initialized()

        # 获取会话信息
        session_result = await manager.graph_store._execute_in_thread(
            lambda: manager.graph_store.conn.execute(
                "MATCH (s:Session {id: $id}) RETURN s",
                {"id": session_id},
            )
        )

        if not session_result or not session_result.has_next():
            return ApiResponse(success=False, error="SESSION_NOT_FOUND", message="会话不存在")

        session_row = session_result.get_next()
        session_node = session_row[0]

        # 获取会话中的实体
        entities_result = await manager.graph_store._execute_in_thread(
            lambda: manager.graph_store.conn.execute(
                """
                MATCH (e:Entity)-[:MENTIONED_IN]->(s:Session {id: $id})
                RETURN e
                ORDER BY e.importance DESC
                LIMIT $limit
                """,
                {"id": session_id, "limit": max_entities},
            )
        )

        nodes = []
        entity_names = []

        # 添加实体节点
        while entities_result.has_next():
            row = entities_result.get_next()
            entity = row[0]
            entity_names.append(entity["name"])
            nodes.append({
                "id": entity["name"],
                "label": "Entity",
                "properties": {
                    "name": entity["name"],
                    "type": entity.get("type", ""),
                    "description": entity.get("description", ""),
                    "importance": entity.get("importance", 0.0),
                    "access_count": entity.get("access_count", 0),
                },
            })

        edges = []

        # 获取实体间的关系
        if include_relations and entity_names:
            relations_result = await manager.graph_store._execute_in_thread(
                lambda: manager.graph_store.conn.execute(
                    """
                    MATCH (e1:Entity)-[r:RELATED_TO]->(e2:Entity)
                    WHERE e1.name IN $names AND e2.name IN $names
                    RETURN e1.name, e2.name, r
                    """,
                    {"names": entity_names},
                )
            )

            while relations_result.has_next():
                row = relations_result.get_next()
                from_name, to_name, rel = row
                edges.append({
                    "id": f"{from_name}-{to_name}",
                    "source": from_name,
                    "target": to_name,
                    "label": "RELATED_TO",
                    "properties": {
                        "relation": rel.get("relation", ""),
                        "strength": rel.get("strength", 0.0),
                        "evidence": rel.get("evidence", ""),
                    },
                })

        return ApiResponse(
            success=True,
            data={
                "session": {
                    "id": session_node["id"],
                    "name": session_node.get("name", ""),
                    "type": session_node.get("type", ""),
                    "created_at": session_node.get("created_at", ""),
                },
                "nodes": nodes,
                "edges": edges,
            },
        )

    except Exception as e:
        return ApiResponse(success=False, error="INTERNAL_ERROR", message=str(e))


@router.get("/global")
async def get_global_graph(
    request: Request,
    entity_types: list[str] = Query(None, description="实体类型过滤"),
    min_importance: float = Query(0.0, description="最小重要性"),
    limit: int = Query(500, description="节点数量限制"),
    offset: int = Query(0, description="分页偏移"),
    _: bool = Depends(verify_key),
):
    """获取全局图谱

    Args:
        entity_types: 实体类型过滤
        min_importance: 最小重要性
        limit: 节点数量限制
        offset: 分页偏移

    Returns:
        全局图谱数据
    """
    try:
        manager = request.app.state.manager
        await manager.ensure_initialized()

        # 构建查询条件
        where_clauses = []
        params = {"limit": limit, "offset": offset}

        if entity_types:
            where_clauses.append("e.type IN $types")
            params["types"] = entity_types

        if min_importance > 0:
            where_clauses.append("e.importance >= $min_importance")
            params["min_importance"] = min_importance

        where_clause = " AND ".join(where_clauses) if where_clauses else "true"

        # 获取实体
        entities_result = await manager.graph_store._execute_in_thread(
            lambda: manager.graph_store.conn.execute(
                f"""
                MATCH (e:Entity)
                WHERE {where_clause}
                RETURN e
                ORDER BY e.importance DESC
                SKIP $offset
                LIMIT $limit
                """,
                params,
            )
        )

        nodes = []
        entity_names = []

        while entities_result.has_next():
            row = entities_result.get_next()
            entity = row[0]
            entity_names.append(entity["name"])
            nodes.append({
                "id": entity["name"],
                "label": "Entity",
                "properties": {
                    "name": entity["name"],
                    "type": entity.get("type", ""),
                    "description": entity.get("description", ""),
                    "importance": entity.get("importance", 0.0),
                    "access_count": entity.get("access_count", 0),
                },
            })

        # 获取关系
        edges = []
        if entity_names:
            relations_result = await manager.graph_store._execute_in_thread(
                lambda: manager.graph_store.conn.execute(
                    """
                    MATCH (e1:Entity)-[r:RELATED_TO]->(e2:Entity)
                    WHERE e1.name IN $names AND e2.name IN $names
                    RETURN e1.name, e2.name, r
                    """,
                    {"names": entity_names},
                )
            )

            while relations_result.has_next():
                row = relations_result.get_next()
                from_name, to_name, rel = row
                edges.append({
                    "id": f"{from_name}-{to_name}",
                    "source": from_name,
                    "target": to_name,
                    "label": "RELATED_TO",
                    "properties": {
                        "relation": rel.get("relation", ""),
                        "strength": rel.get("strength", 0.0),
                    },
                })

        return ApiResponse(
            success=True,
            data={
                "nodes": nodes,
                "edges": edges,
                "total": len(nodes),
            },
        )

    except Exception as e:
        return ApiResponse(success=False, error="INTERNAL_ERROR", message=str(e))


@router.get("/neighbors/{entity_name}")
async def get_entity_neighbors(
    request: Request,
    entity_name: str,
    depth: int = Query(1, description="遍历深度"),
    max_neighbors: int = Query(20, description="最大邻居数"),
    _: bool = Depends(verify_key),
):
    """获取实体邻居

    Args:
        entity_name: 实体名称
        depth: 遍历深度
        max_neighbors: 最大邻居数

    Returns:
        实体及其邻居
    """
    try:
        manager = request.app.state.manager
        await manager.ensure_initialized()

        # 获取中心实体
        center_result = await manager.graph_store._execute_in_thread(
            lambda: manager.graph_store.conn.execute(
                "MATCH (e:Entity {name: $name}) RETURN e",
                {"name": entity_name},
            )
        )

        if not center_result or not center_result.has_next():
            return ApiResponse(success=False, error="ENTITY_NOT_FOUND", message="实体不存在")

        center_entity = center_result.get_next()[0]

        # 获取邻居（depth 层）
        neighbors_result = await manager.graph_store._execute_in_thread(
            lambda: manager.graph_store.conn.execute(
                f"""
                MATCH path = (center:Entity {{name: $name}})-[r:RELATED_TO*1..{depth}]-(neighbor:Entity)
                RETURN DISTINCT neighbor, length(path) as distance, r
                ORDER BY distance, neighbor.importance DESC
                LIMIT $limit
                """,
                {"name": entity_name, "limit": max_neighbors},
            )
        )

        neighbors = []
        while neighbors_result.has_next():
            row = neighbors_result.get_next()
            neighbor, distance, rels = row
            neighbors.append({
                "entity": {
                    "name": neighbor["name"],
                    "type": neighbor.get("type", ""),
                    "description": neighbor.get("description", ""),
                    "importance": neighbor.get("importance", 0.0),
                },
                "distance": distance,
            })

        return ApiResponse(
            success=True,
            data={
                "center": {
                    "name": center_entity["name"],
                    "type": center_entity.get("type", ""),
                    "description": center_entity.get("description", ""),
                    "importance": center_entity.get("importance", 0.0),
                },
                "neighbors": neighbors,
            },
        )

    except Exception as e:
        return ApiResponse(success=False, error="INTERNAL_ERROR", message=str(e))
