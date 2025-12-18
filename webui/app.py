"""FastAPI 应用主文件"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api import entities, graph, relations, search, stats, system


def create_app(manager, config: dict) -> FastAPI:
    """创建 FastAPI 应用

    Args:
        manager: GraphMemoryManager 实例
        config: 插件配置
    """
    app = FastAPI(
        title="GraphMemory WebUI",
        description="图谱记忆可视化管理界面",
        version="0.5.0",
    )

    # CORS 配置
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 存储 manager 和 config 到 app.state
    app.state.manager = manager
    app.state.config = config

    # 注册路由
    app.include_router(graph.router, prefix="/api/graph", tags=["图谱数据"])
    app.include_router(entities.router, prefix="/api/entities", tags=["实体管理"])
    app.include_router(relations.router, prefix="/api/relations", tags=["关系管理"])
    app.include_router(search.router, prefix="/api/search", tags=["搜索功能"])
    app.include_router(stats.router, prefix="/api/stats", tags=["统计分析"])
    app.include_router(system.router, prefix="/api/system", tags=["系统管理"])

    # 静态文件服务（前端构建产物）
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app
