"""搜索功能接口"""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from ..schemas.common import ApiResponse
from ..utils.auth import verify_key

router = APIRouter()


class HybridSearchRequest(BaseModel):
    """混合搜索请求"""

    query: str
    session_id: str | None = None
    top_k: int = 7
    include_evidence: bool = False


@router.post("/hybrid")
async def hybrid_search(
    request: Request,
    search_request: HybridSearchRequest,
    _: bool = Depends(verify_key),
):
    """混合搜索（向量 + 关键词 + 图遍历）

    Args:
        search_request: 搜索请求参数

    Returns:
        搜索结果
    """
    try:
        manager = request.app.state.manager
        await manager.ensure_initialized()

        if not manager.embedding_provider:
            return ApiResponse(
                success=False,
                error="EMBEDDING_NOT_CONFIGURED",
                message="未配置 Embedding Provider，无法进行向量搜索",
            )

        # 生成查询向量
        query_embedding = await manager.embedding_provider.get_embedding(search_request.query)

        # 获取人格 ID（如果指定了会话）
        persona_id = "default"

        # 检索记忆
        memory_text = await manager.retriever.search_memory(
            search_request.query,
            query_embedding,
            search_request.session_id or "",
            persona_id,
            search_request.top_k,
        )

        # 获取匹配的实体
        entities = await manager.graph_store.search_entities(
            search_request.query,
            None,
            search_request.top_k,
        )

        results = []
        for entity in entities:
            results.append({
                "entity": {
                    "name": entity.name,
                    "type": entity.type,
                    "description": entity.description,
                    "importance": entity.importance,
                },
                "score": entity.importance,  # 使用重要性作为分数
                "match_type": "hybrid",
            })

        return ApiResponse(
            success=True,
            data={
                "results": results,
                "formatted_text": memory_text or "未找到相关记忆",
                "query": search_request.query,
            },
        )

    except Exception as e:
        return ApiResponse(success=False, error="INTERNAL_ERROR", message=str(e))


@router.post("/vector")
async def vector_search(
    request: Request,
    search_request: HybridSearchRequest,
    _: bool = Depends(verify_key),
):
    """向量搜索测试

    Args:
        search_request: 搜索请求参数

    Returns:
        向量搜索结果
    """
    try:
        manager = request.app.state.manager
        await manager.ensure_initialized()

        if not manager.embedding_provider:
            return ApiResponse(
                success=False,
                error="EMBEDDING_NOT_CONFIGURED",
                message="未配置 Embedding Provider",
            )

        # 生成查询向量
        query_embedding = await manager.embedding_provider.get_embedding(search_request.query)

        # 向量搜索
        def _search():
            result = manager.graph_store.conn.execute(
                """
                MATCH (e:Entity)
                WHERE e.embedding IS NOT NULL
                RETURN e
                ORDER BY e.importance DESC
                LIMIT $limit
                """,
                {"limit": search_request.top_k},
            )

            entities = []
            while result.has_next():
                row = result.get_next()
                entity = row[0]

                # 计算余弦相似度
                if entity.get("embedding"):
                    import math

                    vec1 = query_embedding
                    vec2 = entity["embedding"]

                    if len(vec1) == len(vec2):
                        dot_product = sum(a * b for a, b in zip(vec1, vec2))
                        norm1 = math.sqrt(sum(a * a for a in vec1))
                        norm2 = math.sqrt(sum(b * b for b in vec2))

                        if norm1 > 0 and norm2 > 0:
                            similarity = dot_product / (norm1 * norm2)
                            entities.append({
                                "entity": {
                                    "name": entity["name"],
                                    "type": entity.get("type", ""),
                                    "description": entity.get("description", ""),
                                    "importance": entity.get("importance", 0.0),
                                },
                                "similarity": similarity,
                            })

            # 按相似度排序
            entities.sort(key=lambda x: x["similarity"], reverse=True)
            return entities[:search_request.top_k]

        results = await manager.graph_store._execute_in_thread(_search)

        return ApiResponse(
            success=True,
            data={
                "results": results,
                "query": search_request.query,
            },
        )

    except Exception as e:
        return ApiResponse(success=False, error="INTERNAL_ERROR", message=str(e))


@router.post("/keyword")
async def keyword_search(
    request: Request,
    search_request: HybridSearchRequest,
    _: bool = Depends(verify_key),
):
    """关键词搜索测试

    Args:
        search_request: 搜索请求参数

    Returns:
        关键词搜索结果
    """
    try:
        manager = request.app.state.manager
        await manager.ensure_initialized()

        # 关键词搜索
        entities = await manager.graph_store.search_entities(
            search_request.query,
            None,
            search_request.top_k,
        )

        results = []
        for entity in entities:
            results.append({
                "entity": {
                    "name": entity.name,
                    "type": entity.type,
                    "description": entity.description,
                    "importance": entity.importance,
                },
                "matched_keywords": [search_request.query],
            })

        return ApiResponse(
            success=True,
            data={
                "results": results,
                "query": search_request.query,
            },
        )

    except Exception as e:
        return ApiResponse(success=False, error="INTERNAL_ERROR", message=str(e))
