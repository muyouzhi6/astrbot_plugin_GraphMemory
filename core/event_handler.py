"""事件处理器"""

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent
from astrbot.api.provider import LLMResponse, ProviderRequest


class EventHandler:
    """事件处理器"""

    def __init__(self, manager, config: dict):
        self.manager = manager
        self.config = config

    async def on_llm_request(self, event: AstrMessageEvent, req: ProviderRequest):
        """在 LLM 请求前注入记忆"""
        await self.manager.inject_memory(event, req)

        # 如果启用了 Function Calling，注册工具
        if self.config.get("enable_function_calling", False):
            await self.manager.ensure_initialized()
            if self.manager.function_calling:
                tool_schema = self.manager.function_calling.get_tool_schema()
                if not hasattr(req, "tools"):
                    req.tools = []
                req.tools.append(tool_schema)
                logger.debug("[GraphMemory] 已注册 Function Calling 工具")

    async def on_user_message(self, event: AstrMessageEvent):
        """监听用户消息"""
        await self.manager.on_user_message(event)

    async def on_llm_response(self, event: AstrMessageEvent, resp: LLMResponse):
        """监听 LLM 响应"""
        # 处理 Function Calling
        if self.config.get("enable_function_calling", False) and hasattr(resp, "tool_calls"):
            if resp.tool_calls:
                await self.manager.ensure_initialized()
                session_id = event.unified_msg_origin
                persona_id = await self.manager._get_persona_id(event)

                for tool_call in resp.tool_calls:
                    tool_name = tool_call.get("name", "")
                    tool_args = tool_call.get("arguments", {})

                    if tool_name == "search_memory":
                        result = await self.manager.function_calling.handle_tool_call(
                            tool_name, tool_args, session_id, persona_id
                        )
                        # 将结果添加到响应中
                        if not hasattr(resp, "tool_results"):
                            resp.tool_results = []
                        resp.tool_results.append({
                            "tool_call_id": tool_call.get("id", ""),
                            "result": result,
                        })

        if resp.completion_text:
            await self.manager.on_bot_message(event, resp.completion_text)
