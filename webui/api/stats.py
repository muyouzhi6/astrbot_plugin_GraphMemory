"""统计分析接口"""

from fastapi import APIRouter, Depends, Request

from ..schemas.common import ApiResponse
from ..utils.auth import verify_key

router = APIRouter()


@router.get("/overview")
async def get_stats_overview(
    request: Request,
    _: bool = Depends(verify_key),
):
    """获取统计概览"""
    try:
        manager = request.app.state.manager
        await manager.ensure_initialized()

        stats = await manager.get_stats()

        return ApiResponse(
            success=True,
            data={
                "total_entities": stats.get("entities", 0),
                "total_relations": stats.get("relations", 0),
                "total_sessions": stats.get("sessions", 0),
                "total_users": stats.get("users", 0),
            },
        )

    except Exception as e:
        return ApiResponse(success=False, error="INTERNAL_ERROR", message=str(e))


@router.get("/entity-types")
async def get_entity_type_distribution(
    request: Request,
    _: bool = Depends(verify_key),
):
    """获取实体类型分布"""
    try:
        manager = request.app.state.manager
        await manager.ensure_initialized()

        distribution = await manager.graph_store.get_entity_type_distribution()

        return ApiResponse(
            success=True,
            data={"distribution": distribution},
        )

    except Exception as e:
        return ApiResponse(success=False, error="INTERNAL_ERROR", message=str(e))


@router.get("/timeline")
async def get_timeline_stats(
    request: Request,
    _: bool = Depends(verify_key),
):
    """获取时间线统计"""
    try:
        manager = request.app.state.manager
        await manager.ensure_initialized()

        timeline = await manager.graph_store.get_timeline_stats()

        return ApiResponse(
            success=True,
            data={"timeline": timeline},
        )

    except Exception as e:
        return ApiResponse(success=False, error="INTERNAL_ERROR", message=str(e))
