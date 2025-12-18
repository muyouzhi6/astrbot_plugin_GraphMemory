"""关系管理接口"""

from fastapi import APIRouter, Depends, Query, Request

from ..schemas.common import ApiResponse
from ..utils.auth import verify_key

router = APIRouter()


@router.get("")
async def list_relations(
    request: Request,
    from_entity: str | None = Query(None, description="起点实体过滤"),
    to_entity: str | None = Query(None, description="终点实体过滤"),
    min_strength: float = Query(0.0, description="最小强度"),
    limit: int = Query(50, description="每页数量"),
    offset: int = Query(0, description="分页偏移"),
    _: bool = Depends(verify_key),
):
    """获取关系列表

    Args:
        from_entity: 起点实体过滤
        to_entity: 终点实体过滤
        min_strength: 最小强度
        limit: 每页数量
        offset: 分页偏移

    Returns:
        关系列表
    """
    try:
        manager = request.app.state.manager
        await manager.ensure_initialized()

        # 构建查询条件
        where_clauses = []
        params = {}

        if from_entity:
            where_clauses.append("e1.name = $from_entity")
            params["from_entity"] = from_entity

        if to_entity:
            where_clauses.append("e2.name = $to_entity")
            params["to_entity"] = to_entity

        if min_strength > 0:
            where_clauses.append("r.strength >= $min_strength")
            params["min_strength"] = min_strength

        where_clause = " AND ".join(where_clauses) if where_clauses else "true"

        # 获取总数
        def _count():
            result = manager.graph_store.conn.execute(
                f"""
                MATCH (e1:Entity)-[r:RELATED_TO]->(e2:Entity)
                WHERE {where_clause}
                RETURN count(r) as total
                """,
                params,
            )
            return result.get_next()[0] if result.has_next() else 0

        total = await manager.graph_store._execute_in_thread(_count)

        # 获取关系列表
        params["limit"] = limit
        params["offset"] = offset

        def _list():
            result = manager.graph_store.conn.execute(
                f"""
                MATCH (e1:Entity)-[r:RELATED_TO]->(e2:Entity)
                WHERE {where_clause}
                RETURN e1.name, e2.name, r
                ORDER BY r.strength DESC
                SKIP $offset
                LIMIT $limit
                """,
                params,
            )

            relations = []
            while result.has_next():
                row = result.get_next()
                from_name, to_name, rel = row
                relations.append({
                    "from": from_name,
                    "to": to_name,
                    "relation": rel.get("relation", ""),
                    "strength": rel.get("strength", 0.0),
                    "evidence": rel.get("evidence", ""),
                    "created_at": rel.get("created_at", ""),
                    "last_updated": rel.get("last_updated", ""),
                })

            return relations

        relations = await manager.graph_store._execute_in_thread(_list)

        return ApiResponse(
            success=True,
            data={
                "relations": relations,
                "total": total,
                "limit": limit,
                "offset": offset,
            },
        )

    except Exception as e:
        return ApiResponse(success=False, error="INTERNAL_ERROR", message=str(e))


@router.delete("")
async def delete_relation(
    request: Request,
    from_entity: str = Query(..., description="起点实体"),
    to_entity: str = Query(..., description="终点实体"),
    _: bool = Depends(verify_key),
):
    """删除关系

    Args:
        from_entity: 起点实体
        to_entity: 终点实体

    Returns:
        删除结果
    """
    try:
        manager = request.app.state.manager
        await manager.ensure_initialized()

        def _delete():
            manager.graph_store.conn.execute(
                """
                MATCH (e1:Entity {name: $from})-[r:RELATED_TO]->(e2:Entity {name: $to})
                DELETE r
                """,
                {"from": from_entity, "to": to_entity},
            )
            return True

        await manager.graph_store._execute_in_thread(_delete)

        return ApiResponse(
            success=True,
            message=f"已删除关系: {from_entity} -> {to_entity}",
        )

    except Exception as e:
        return ApiResponse(success=False, error="INTERNAL_ERROR", message=str(e))
