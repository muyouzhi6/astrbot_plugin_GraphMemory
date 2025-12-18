"""系统管理接口"""

import json
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from ..schemas.common import ApiResponse
from ..utils.auth import verify_key

router = APIRouter()


class ImportRequest(BaseModel):
    """导入请求"""

    content: str
    merge: bool = True


@router.get("/status")
async def get_system_status(
    request: Request,
    _: bool = Depends(verify_key),
):
    """获取系统状态"""
    try:
        config = request.app.state.config
        manager = request.app.state.manager

        # 获取统计信息
        stats = {}
        if manager._core_initialized:
            stats = await manager.get_stats()

        return ApiResponse(
            success=True,
            data={
                "version": "0.5.0",
                "embedding_provider": config.get("embedding_provider_id", ""),
                "llm_provider": config.get("llm_provider_id", ""),
                "total_entities": stats.get("entities", 0),
                "total_relations": stats.get("relations", 0),
                "total_sessions": stats.get("sessions", 0),
            },
        )

    except Exception as e:
        return ApiResponse(success=False, error="INTERNAL_ERROR", message=str(e))


@router.get("/export")
async def export_graph(
    request: Request,
    persona_id: str | None = Query(None, description="人格ID"),
    _: bool = Depends(verify_key),
):
    """导出图谱

    Args:
        persona_id: 人格ID，留空导出全部

    Returns:
        导出的图谱数据
    """
    try:
        manager = request.app.state.manager
        await manager.ensure_initialized()

        data = await manager.export_graph(persona_id)

        return ApiResponse(
            success=True,
            data={
                "format": "json",
                "content": json.dumps(data, ensure_ascii=False, indent=2),
                "exported_at": datetime.now().isoformat(),
                "entity_count": len(data.get("entities", [])),
                "relation_count": len(data.get("relations", [])),
            },
        )

    except Exception as e:
        return ApiResponse(success=False, error="INTERNAL_ERROR", message=str(e))


@router.post("/import")
async def import_graph(
    request: Request,
    import_request: ImportRequest,
    _: bool = Depends(verify_key),
):
    """导入图谱

    Args:
        import_request: 导入请求

    Returns:
        导入结果
    """
    try:
        manager = request.app.state.manager
        await manager.ensure_initialized()

        data = json.loads(import_request.content)
        entity_count, relation_count = await manager.import_graph(
            data,
            import_request.merge,
        )

        return ApiResponse(
            success=True,
            data={
                "imported_entities": entity_count,
                "imported_relations": relation_count,
            },
            message="导入成功",
        )

    except json.JSONDecodeError:
        return ApiResponse(
            success=False,
            error="INVALID_JSON",
            message="无效的 JSON 格式",
        )
    except Exception as e:
        return ApiResponse(success=False, error="INTERNAL_ERROR", message=str(e))


@router.post("/cleanup")
async def cleanup_graph(
    request: Request,
    action: str = Query(..., description="清理动作"),
    threshold: float = Query(0.1, description="阈值"),
    _: bool = Depends(verify_key),
):
    """清理图谱

    Args:
        action: 清理动作 (prune_low_importance, apply_decay)
        threshold: 阈值

    Returns:
        清理结果
    """
    try:
        manager = request.app.state.manager
        await manager.ensure_initialized()

        if action == "prune_low_importance":
            count = await manager.graph_store.prune_low_importance_entities(threshold)
            return ApiResponse(
                success=True,
                data={"removed_entities": count},
                message=f"已清理 {count} 个低重要性实体",
            )

        elif action == "apply_decay":
            await manager.graph_store.apply_time_decay(threshold)
            return ApiResponse(
                success=True,
                message="已应用时间衰减",
            )

        else:
            return ApiResponse(
                success=False,
                error="INVALID_ACTION",
                message=f"无效的清理动作: {action}",
            )

    except Exception as e:
        return ApiResponse(success=False, error="INTERNAL_ERROR", message=str(e))
