"""GraphMemory 插件入口"""

import asyncio
import platform

from astrbot.api import logger

if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.provider import LLMResponse, ProviderRequest
from astrbot.api.star import Context, Star, StarTools, register

from .core.manager import GraphMemoryManager


@register(
    "GraphMemory",
    "lxfight",
    "基于图数据库的长期记忆插件 (v0.3.0)",
    version="0.3.0",
)
class GraphMemory(Star):
    """GraphMemory 插件

    功能:
    - 自动知识提取
    - 智能记忆检索
    - 人格分层共享
    - 时间衰减机制
    """

    def __init__(self, context: Context, config: dict | None = None):
        super().__init__(context)
        self.config = config or {}

        # 获取插件数据目录（必须在 main.py 中调用）
        plugin_data_path = StarTools.get_data_dir()

        # 初始化核心管理器
        self.manager = GraphMemoryManager(context, plugin_data_path, self.config)

        logger.info("[GraphMemory] 插件构造完成")

    async def initialize(self):
        """插件初始化（在 Provider 加载后调用）"""
        logger.info("[GraphMemory] initialize() 被调用，核心模块将延迟初始化")

    async def terminate(self):
        """插件终止"""
        await self.manager.terminate()

    # ==================== 事件处理 ====================

    @filter.on_llm_request()
    async def inject_memory(self, event: AstrMessageEvent, req: ProviderRequest):
        """在 LLM 请求前注入记忆"""
        await self.manager.inject_memory(event, req)

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_user_message(self, event: AstrMessageEvent):
        """监听用户消息"""
        await self.manager.on_user_message(event)

    @filter.on_llm_response()
    async def on_llm_resp(self, event: AstrMessageEvent, resp: LLMResponse):
        """监听 LLM 响应"""
        if resp.completion_text:
            await self.manager.on_bot_message(event, resp.completion_text)

    # ==================== 指令处理 ====================

    @filter.command("memory_stat")
    async def cmd_stat(self, event: AstrMessageEvent):
        """显示图谱统计信息"""
        try:
            stats = await self.manager.get_stats()
            text = f"""图谱统计信息:
- 用户数: {stats.get('users', 0)}
- 会话数: {stats.get('sessions', 0)}
- 实体数: {stats.get('entities', 0)}
- 关系数: {stats.get('relations', 0)}
"""
            yield text
        except Exception as e:
            logger.error(f"[GraphMemory] 获取统计信息失败: {e}", exc_info=True)
            yield f"获取统计信息失败: {e}"
