"""实体管理接口"""

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from ..schemas.common import ApiResponse
from ..utils.auth import verify_key

router = APIRouter()


class EntityCreate(BaseModel):
    """创建实体请求"""

    name: str
    type: str
    description: str
    importance: float = 1.0


class EntityUpdate(BaseModel):
    """更新实体请求"""

    type: str | None = None
    description: str | None = None
    importance: float | None = None


@router.get("")
async def list_entities(
    request: Request,
    type: str | None = Query(None, description="实体类型过滤"),
    search: str | None = Query(None, description="名称搜索"),
    sort_by: str = Query("importance", description="排序字段"),
    order: str = Query("desc", description="排序方向"),
    limit: int = Query(50, description="每页数量"),
    offset: int = Query(0, description="分页偏移"),
    _: bool = Depends(verify_key),
):
    """获取实体列表

    Args:
        type: 实体类型过滤
        search: 名称搜索
        sort_by: 排序字段
        order: 排序方向
        limit: 每页数量
        offset: 分页偏移

    Returns:
        实体列表
    """
    try:
        manager = request.app.state.manager
        await manager.ensure_initialized()

        # 构建查询条件
        where_clauses = []
        params = {}

        if type:
            where_clauses.append("e.type = $type")
            params["type"] = type

        if search:
            where_clauses.append("e.name CONTAINS $search")
            params["search"] = search

        where_clause = " AND ".join(where_clauses) if where_clauses else "true"

        # 排序
        order_clause = f"e.{sort_by} {'DESC' if order == 'desc' else 'ASC'}"

        # 获取总数
        count_result = await manager.graph_store._execute_in_thread(
            lambda: manager.graph_store.conn.execute(
                f"MATCH (e:Entity) WHERE {where_clause} RETURN count(e) as total",
                params,
            )
        )
        total = count_result.get_next()[0] if count_result.has_next() else 0

        # 获取实体列表
        params["limit"] = limit
        params["offset"] = offset

        entities_result = await manager.graph_store._execute_in_thread(
            lambda: manager.graph_store.conn.execute(
                f"""
                MATCH (e:Entity)
                WHERE {where_clause}
                RETURN e
                ORDER BY {order_clause}
                SKIP $offset
                LIMIT $limit
                """,
                params,
            )
        )

        entities = []
        while entities_result.has_next():
            row = entities_result.get_next()
            entity = row[0]
            entities.append({
                "name": entity["name"],
                "type": entity.get("type", ""),
                "description": entity.get("description", ""),
                "importance": entity.get("importance", 0.0),
                "access_count": entity.get("access_count", 0),
                "created_at": entity.get("created_at", ""),
                "last_accessed": entity.get("last_accessed", ""),
            })

        return ApiResponse(
            success=True,
            data={
                "entities": entities,
                "total": total,
                "limit": limit,
                "offset": offset,
            },
        )

    except Exception as e:
        return ApiResponse(success=False, error="INTERNAL_ERROR", message=str(e))


@router.get("/{entity_name}")
async def get_entity(
    request: Request,
    entity_name: str,
    _: bool = Depends(verify_key),
):
    """获取单个实体详情

    Args:
        entity_name: 实体名称

    Returns:
        实体详情
    """
    try:
        manager = request.app.state.manager
        await manager.ensure_initialized()

        # 获取实体
        entity_result = await manager.graph_store._execute_in_thread(
            lambda: manager.graph_store.conn.execute(
                "MATCH (e:Entity {name: $name}) RETURN e",
                {"name": entity_name},
            )
        )

        if not entity_result or not entity_result.has_next():
            return ApiResponse(success=False, error="ENTITY_NOT_FOUND", message="实体不存在")

        entity = entity_result.get_next()[0]

        # 获取关系
        relations = await manager.get_entity_relations(entity_name)

        # 获取提及记录
        mentions_result = await manager.graph_store._execute_in_thread(
            lambda: manager.graph_store.conn.execute(
                """
                MATCH (e:Entity {name: $name})-[m:MENTIONED_IN]->(s:Session)
                RETURN s.id, s.name, m.mention_count, m.last_mentioned
                ORDER BY m.last_mentioned DESC
                """,
                {"name": entity_name},
            )
        )

        mentioned_in = []
        while mentions_result.has_next():
            row = mentions_result.get_next()
            mentioned_in.append({
                "session_id": row[0],
                "session_name": row[1],
                "mention_count": row[2],
                "last_mentioned": row[3],
            })

        return ApiResponse(
            success=True,
            data={
                "entity": {
                    "name": entity["name"],
                    "type": entity.get("type", ""),
                    "description": entity.get("description", ""),
                    "importance": entity.get("importance", 0.0),
                    "access_count": entity.get("access_count", 0),
                    "created_at": entity.get("created_at", ""),
                    "last_accessed": entity.get("last_accessed", ""),
                },
                "relations": relations,
                "mentioned_in": mentioned_in,
            },
        )

    except Exception as e:
        return ApiResponse(success=False, error="INTERNAL_ERROR", message=str(e))


@router.delete("/{entity_name}")
async def delete_entity(
    request: Request,
    entity_name: str,
    cascade: bool = Query(True, description="是否级联删除关系"),
    _: bool = Depends(verify_key),
):
    """删除实体

    Args:
        entity_name: 实体名称
        cascade: 是否级联删除关系

    Returns:
        删除结果
    """
    try:
        manager = request.app.state.manager
        await manager.ensure_initialized()

        success, relation_count = await manager.delete_entity(entity_name)

        if success:
            return ApiResponse(
                success=True,
                message=f"实体已删除，同时删除了 {relation_count} 条关系",
            )
        else:
            return ApiResponse(success=False, error="DELETE_FAILED", message="删除失败")

    except Exception as e:
        return ApiResponse(success=False, error="INTERNAL_ERROR", message=str(e))
