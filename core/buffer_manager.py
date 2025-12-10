import asyncio
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent

from .monitoring_service import monitoring_service


@dataclass
class BufferMessage:
    """
    一个标准化的内部消息对象，用于在缓冲区中统一表示用户和机器人的消息。
    这简化了后续处理，使其不依赖于原始的事件格式。
    """

    sender_id: str      # 发送者ID (用户ID 或 Bot ID)
    sender_name: str    # 发送者名称 (用户名 或 Bot名)
    content: str        # 消息的纯文本内容
    timestamp: float    # 消息的时间戳
    role: str           # 角色: 'user' 或 'assistant'
    persona_id: str     # 消息所属的人格ID
    is_group: bool = False  # 是否为群聊消息

    def to_log_str(self) -> str:
        """
        将消息转换为 LLM 易于解析的日志格式。
        格式: [role:sender_name:sender_id]: content
        """
        prefix = f"[{self.role}:{self.sender_name}:{self.sender_id}]"
        return f"{prefix}: {self.content}"


class SessionBuffer:
    """
    管理单个会话的消息缓冲区。
    它会收集消息，直到达到大小限制或时间限制，然后一次性清空。
    """
    def __init__(self, session_id: str, max_size: int = 10, max_seconds: int = 60):
        self.session_id = session_id
        self.max_size = max_size          # 缓冲区的最大消息条数
        self.max_seconds = max_seconds    # 消息在缓冲区中最长的等待时间

        self.is_group: bool = False       # 标记该会话是否为群聊
        self.current_persona_id: str | None = None  # 记录当前Buffer所属的人格ID

        self._buffer: list[BufferMessage] = []
        self._last_flush_time = time.time()
        self._last_activity_time = time.time()

    def add(self, message: BufferMessage) -> bool:
        """
        向缓冲区添加一条消息。

        Args:
            message (BufferMessage): 要添加的消息对象。

        Returns:
            bool: 如果添加后达到了大小限制，返回 True，表示应立即刷新。
        """
        # 如果是该Buffer的第一条消息，记录会话状态
        if not self._buffer:
            self.current_persona_id = message.persona_id
            self.is_group = message.is_group

        self._buffer.append(message)
        self._last_activity_time = time.time()

        # 检查是否达到条数限制
        if len(self._buffer) >= self.max_size:
            logger.debug(f"[GraphMemory DEBUG] 会话 {self.session_id} 的缓冲区已满 (大小: {self.max_size})")
            return True
        return False

    def should_flush_by_time(self) -> bool:
        """检查是否因为超时而需要刷新缓冲区。"""
        if not self._buffer:
            return False
        # 如果当前有未处理消息，且距离上次活跃时间超过了阈值
        return (time.time() - self._last_activity_time) >= self.max_seconds

    def flush(self) -> str:
        """
        清空当前缓冲区，并将所有消息格式化为一个文本块。

        Returns:
            str: 格式化后的对话文本块。
        """
        if not self._buffer:
            return ""

        # 将缓冲区内的消息连接成一个多行字符串
        lines = [msg.to_log_str() for msg in self._buffer]
        text_block = "\n".join(lines)

        log_message = f"[GraphMemory Buffer] 正在刷新会话 {self.session_id} 的 {len(lines)} 条消息 (人格: {self.current_persona_id})"
        logger.debug(log_message)
        asyncio.create_task(monitoring_service.add_task(f"刷新会话 {self.session_id} 的缓冲区"))

        # 重置缓冲区状态
        self._buffer.clear()
        self._last_flush_time = time.time()

        return text_block

    @property
    def message_count(self) -> int:
        """返回当前缓冲区中的消息数量。"""
        return len(self._buffer)


# 定义回调函数类型：当缓冲区flush时，调用此异步函数处理文本块。
# 参数: (session_id, text_content, is_group, persona_id)
FlushCallback = Callable[[str, str, bool, str], Coroutine[Any, Any, None]]


class BufferManager:
    """
    管理所有会话的缓冲区。
    这是一个核心组件，用于批量处理消息以提高效率。它避免了为每条消息都调用昂贵的LLM提取操作。
    它会为每个会话创建一个 SessionBuffer，并根据大小、时间或上下文切换来触发刷新。
    """
    def __init__(
        self,
        flush_callback: FlushCallback,
        max_size: int = 10,
        max_wait_seconds: int = 60,
    ):
        self.buffers: dict[str, SessionBuffer] = {}  # 存储所有会话的缓冲区
        self.flush_callback = flush_callback         # 刷新时调用的异步函数
        self.max_size = max_size                     # 默认的最大缓冲区大小
        self.max_wait_seconds = max_wait_seconds     # 默认的最大等待时间
        self._stop_event = asyncio.Event()
        self._timer_task = None

    async def startup(self):
        """启动后台任务。"""
        if not self._timer_task:
            self._timer_task = asyncio.create_task(self._time_checker())

    def _get_session_key(self, event: AstrMessageEvent) -> str:
        """
        根据事件计算会话的唯一标识符。
        使用 `unified_msg_origin`，其格式为 `platform_name:message_type:session_id`。
        """
        return event.unified_msg_origin

    def _outline_chain(self, chain: list) -> str:
        """
        将复杂的消息链（包含图片、At、表情等）转换为带有占位符的纯文本字符串。
        这使得LLM可以在不处理二进制内容的情况下理解消息结构。
        """
        if not chain:
            return ""

        parts = []
        for i in chain:
            # 使用 .type 属性进行分派，这比 isinstance 或 __class__.__name__ 更健壮
            comp_type = getattr(i, "type", "Unknown")

            if comp_type == "Plain":
                # 优先使用 .text 属性，如果不存在则尝试字符串化
                parts.append(getattr(i, "text", str(i)))
            elif comp_type == "Image":
                parts.append("[图片]")
            elif comp_type == "Face":
                parts.append(f"[表情:{getattr(i, 'id', '')}]")
            elif comp_type == "At":
                parts.append(f"[At:{getattr(i, 'qq', '')}]")
            elif comp_type == "AtAll":
                parts.append("[At:全体成员]")
            elif comp_type == "Forward":
                parts.append("[转发消息]")
            elif comp_type == "Reply":
                message_str = getattr(i, "message_str", "")
                sender_nickname = getattr(i, "sender_nickname", "")
                if message_str:
                    parts.append(f"[引用消息({sender_nickname}: {message_str})]")
                else:
                    parts.append("[引用消息]")
            else:
                # 兼容未知组件类型
                parts.append(f"[{comp_type}]")
            parts.append(" ")
        return "".join(parts).strip()

    async def add_user_message(self, event: AstrMessageEvent, persona_id: str):
        """处理来自用户的消息，并将其添加到相应的缓冲区。"""
        session_id = self._get_session_key(event)
        is_group = bool(event.get_group_id())

        # 使用 get_message_outline 获取包含占位符的消息内容
        content = event.get_message_outline()

        logger.debug(f"[GraphMemory DEBUG] 向缓冲区添加用户消息: {content[:50]}... (会话: {session_id}, 人格: {persona_id})")

        msg = BufferMessage(
            sender_id=event.get_sender_id(),
            sender_name=event.get_sender_name(),
            content=content,
            timestamp=time.time(),
            role="user",
            persona_id=persona_id,
            is_group=is_group
        )
        await self._push_to_buffer(session_id, msg)

    async def add_bot_message(self, event: AstrMessageEvent, persona_id: str, content: str | None = None):
        """处理来自机器人的消息，并将其添加到相应的缓冲区。"""
        session_id = self._get_session_key(event)

        bot_content = ""
        if content:
            bot_content = content
        else:
            # 兼容旧方式，从事件结果中获取 Bot 回复的内容
            result = event.get_result()
            if not result:
                return

            # 使用鸭子类型检查：如果有 chain 属性，就当作 MessageEventResult 处理
            if hasattr(result, "chain") and result.chain:
                bot_content = self._outline_chain(result.chain)
            elif isinstance(result, str):
                bot_content = result
            else:
                return

        if not bot_content:
            return

        logger.debug(f"[GraphMemory DEBUG] 向缓冲区添加机器人消息: {bot_content[:50]}... (会话: {session_id}, 人格: {persona_id})")

        msg = BufferMessage(
            sender_id=event.message_obj.self_id,  # Bot 自己的 ID
            sender_name="Bot",
            content=bot_content,
            timestamp=time.time(),
            role="assistant",
            persona_id=persona_id,
            is_group=bool(event.get_group_id())
        )
        await self._push_to_buffer(session_id, msg)

    async def _push_to_buffer(self, session_id: str, msg: BufferMessage):
        """
        内部方法：将消息推入缓冲区，并处理上下文切换和缓冲区溢出。
        """
        if session_id not in self.buffers:
            self.buffers[session_id] = SessionBuffer(
                session_id, self.max_size, self.max_wait_seconds
            )

        buffer = self.buffers[session_id]

        # 检查人格是否发生变化 (上下文切换)
        # 如果缓冲区中已有消息，且新消息的人格ID与缓冲区的当前人格ID不一致
        if buffer.message_count > 0 and buffer.current_persona_id != msg.persona_id:
             logger.debug(
                f"[GraphMemory Buffer] 会话 {session_id} 检测到人格切换 "
                f"({buffer.current_persona_id} -> {msg.persona_id})。正在刷新旧的缓冲区。"
            )
             # 强制刷新旧的缓冲区
             old_persona = buffer.current_persona_id
             is_group = buffer.is_group
             text = buffer.flush()
             if text and old_persona: # 确保有内容和人格ID
                 await self.flush_callback(session_id, text, is_group, old_persona)

        # 此时缓冲区为空（或者是新建的，或者是刚刷新过的），add() 会重置人格ID
        should_flush = buffer.add(msg)

        # 如果因为达到大小限制而需要刷新
        if should_flush:
            logger.debug(
                f"[GraphMemory Buffer] 会话 {session_id} 达到大小限制 ({self.max_size})。正在刷新。"
            )
            current_persona = buffer.current_persona_id
            is_group = buffer.is_group
            text = buffer.flush()
            if text and current_persona:
                await self.flush_callback(session_id, text, is_group, current_persona)

    async def _time_checker(self):
        """后台任务：每隔一段时间检查是否有因超时而需要刷新的缓冲区。"""
        while not self._stop_event.is_set():
            try:
                await asyncio.sleep(5)  # 每5秒轮询一次

                # 遍历所有缓冲区的副本以允许在迭代中修改
                for session_id, buffer in list(self.buffers.items()):
                    if buffer.should_flush_by_time():
                        logger.debug(
                            f"[GraphMemory Buffer] 会话 {session_id} 达到时间限制。正在刷新。"
                        )
                        # 保存状态用于回调
                        persona_id = buffer.current_persona_id
                        is_group = buffer.is_group

                        text = buffer.flush()
                        if text and persona_id:
                            # 异步调用回调，避免阻塞检查循环
                            asyncio.create_task(self.flush_callback(session_id, text, is_group, persona_id))
            except Exception as e:
                logger.error(f"[GraphMemory Buffer] 定时检查循环出错: {e}")

    async def shutdown(self):
        """关闭管理器，确保所有剩余的消息都被处理。"""
        self._stop_event.set()
        if self._timer_task:
            self._timer_task.cancel()

        # 在关闭时将所有缓冲区中残留的消息强制刷新
        logger.info("[GraphMemory Buffer] 正在关闭并刷新所有剩余的缓冲区...")
        for session_id, buffer in self.buffers.items():
            persona_id = buffer.current_persona_id
            is_group = buffer.is_group
            text = buffer.flush()
            if text and persona_id:
                await self.flush_callback(session_id, text, is_group, persona_id)
