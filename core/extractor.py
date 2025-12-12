"""
该模块定义了 `KnowledgeExtractor` 类，负责与大语言模型（LLM）交互，
以从非结构化文本中提取结构化信息、重写查询和生成摘要。
"""

import json
import time
from dataclasses import dataclass, field
from typing import Any

from astrbot.api import logger
from astrbot.api.star import Context

from .graph_entities import (
    EntityNode,
    MentionsRel,
    MessageNode,
    RelatedToRel,
    SessionNode,
    UserNode,
)
from .prompts import (
    EXTRACTION_PROMPT,
    INTERMEDIATE_MEMORY_PROMPT,
    KNOWLEDGE_EXTRACTION_FROM_SUMMARY_PROMPT,
    MEMORY_COMPRESSION_PROMPT,
    QUERY_REWRITING_PROMPT,
    SUMMARIZATION_PROMPT,
)


@dataclass
class ExtractedData:
    """
    一个数据类，用于封装从 LLM 提取并解析后的结构化图数据。
    这为后续的图数据库操作提供了一个清晰、类型安全的数据结构。
    """

    users: list[UserNode] = field(default_factory=list)
    sessions: list[SessionNode] = field(default_factory=list)
    messages: list[MessageNode] = field(default_factory=list)
    entities: list[EntityNode] = field(default_factory=list)
    relations: list[RelatedToRel] = field(default_factory=list)
    mentions: list[MentionsRel] = field(default_factory=list)


@dataclass
class ExtractedKnowledge:
    """
    一个数据类，用于封装从摘要中提取的纯知识（实体和关系）。
    """

    entities: list[EntityNode] = field(default_factory=list)
    relations: list[RelatedToRel] = field(default_factory=list)


class KnowledgeExtractor:
    """
    知识提取器，负责所有与 LLM 相关的文本处理任务。
    它通过调用 LLM API，将非结构化的对话文本转换为结构化的图数据，
    并执行查询重写和文本摘要等辅助任务。
    """

    def __init__(
        self,
        context: Context,
        llm_provider_id: str | None,
        embedding_provider: Any | None,
    ):
        """
        初始化 KnowledgeExtractor。

        Args:
            context (Context): AstrBot 的上下文对象。
            llm_provider_id (str | None): 用于提取、重写和摘要的默认 LLM Provider ID。
            embedding_provider (Any | None): Embedding Provider 实例，可以为 None。
        """
        self.context = context
        self.llm_provider_id = llm_provider_id
        self.embedding_provider = embedding_provider

    def set_embedding_provider(self, embedding_provider: Any):
        """延迟设置 embedding provider。"""
        self.embedding_provider = embedding_provider

    async def extract(
        self, text_block: str, session_id: str, session_name: str, is_group: bool
    ) -> ExtractedData | None:
        """
        从给定的文本块中提取结构化知识。

        此方法调用 LLM，使用 `EXTRACTION_PROMPT` 指导模型从对话日志中识别
        用户、消息、实体和它们之间的关系，并以 JSON 格式返回。
        会话信息直接从传入的参数构建，不依赖 LLM。

        Args:
            text_block (str): 从缓冲区刷新的对话文本块。
            session_id (str): 当前的会话 ID。
            session_name (str): 当前的会话名称。
            is_group (bool): 是否为群聊。

        Returns:
            ExtractedData | None: 如果成功，返回包含提取数据的对象；否则返回 None。
        """
        if not text_block.strip():
            return None

        # 直接根据传入的精确元数据构建 SessionNode
        session_node = SessionNode(
            id=session_id, name=session_name, type="GROUP" if is_group else "PRIVATE"
        )

        start_time = time.time()

        # 确定要使用的 LLM Provider ID
        provider_id = self.llm_provider_id
        if not provider_id:
            provider_id = await self.context.get_current_chat_provider_id(session_id)

        if not provider_id:
            logger.warning(
                f"[GraphMemory] 在会话 {session_id} 中没有可用的 provider 进行提取。"
            )
            return None

        prompt = EXTRACTION_PROMPT.format(text=text_block)

        try:
            # 调用 LLM 生成结构化数据
            resp = await self.context.llm_generate(
                chat_provider_id=provider_id, prompt=prompt
            )
            if not resp or not resp.completion_text:
                logger.warning("[GraphMemory] LLM 为提取任务返回了空响应。")
                return None

            raw_text = resp.completion_text
            logger.debug(f"[GraphMemory DEBUG] LLM 原始提取响应:\n{raw_text}")

            # 从 LLM 的响应中稳健地解析 JSON
            json_str = self._find_json_blob(raw_text)
            if not json_str:
                logger.error(
                    f"[GraphMemory] 未能在 LLM 响应中找到有效的 JSON。原始文本: {raw_text}"
                )
                return None
            data = json.loads(json_str)

            # 为从 LLM 返回的消息添加缺失的元数据
            current_timestamp = int(time.time())
            messages_from_llm = data.get("messages", [])
            processed_messages = [
                MessageNode(
                    **m,
                    session_id=session_id,
                    # LLM 可能不会返回时间戳，因此我们使用当前时间作为后备
                    timestamp=m.get("timestamp", current_timestamp),
                )
                for m in messages_from_llm
            ]

            # 将解析后的字典数据填充到 ExtractedData 对象中
            extracted_data = ExtractedData(
                users=[UserNode(**u) for u in data.get("users", [])],
                sessions=[session_node],  # 使用我们直接创建的、准确的会话节点
                messages=processed_messages,
                entities=[EntityNode(**e) for e in data.get("entities", [])],
                relations=[RelatedToRel(**r) for r in data.get("relations", [])],
                mentions=[MentionsRel(**m) for m in data.get("mentions", [])],
            )

            logger.info(
                f"[GraphMemory] 提取完成，耗时 {time.time() - start_time:.2f}s。"
            )
            return extracted_data

        except json.JSONDecodeError:
            logger.error(
                f"[GraphMemory] 提取过程中发生 JSON 解析错误。原始文本: {raw_text}"
            )
            return None
        except Exception as e:
            logger.error(f"[GraphMemory] LLM 提取错误: {e}", exc_info=True)
            return None

    async def extract_from_summary(
        self, summary_text: str, provider_id: str | None = None
    ) -> ExtractedKnowledge | None:
        """
        从给定的摘要文本中提取结构化知识（仅实体和关系）。

        Args:
            summary_text (str): 从记忆片段中获取的摘要文本。
            provider_id (str | None): 用于此任务的 LLM Provider ID。

        Returns:
            ExtractedKnowledge | None: 如果成功，返回包含提取数据的对象；否则返回 None。
        """
        if not summary_text.strip():
            return None

        prompt = KNOWLEDGE_EXTRACTION_FROM_SUMMARY_PROMPT.format(text=summary_text)
        effective_provider_id = provider_id or self.llm_provider_id
        if not effective_provider_id:
            logger.warning("[GraphMemory] 没有可用的 provider 从摘要中提取知识。")
            return None

        try:
            resp = await self.context.llm_generate(
                chat_provider_id=effective_provider_id, prompt=prompt
            )
            if not resp or not resp.completion_text:
                logger.warning("[GraphMemory] LLM 为摘要提取任务返回了空响应。")
                return None

            raw_text = resp.completion_text
            json_str = self._find_json_blob(raw_text)
            if not json_str:
                logger.error(
                    f"[GraphMemory] 未能在摘要提取响应中找到 JSON。原始文本: {raw_text}"
                )
                return None

            data = json.loads(json_str)

            return ExtractedKnowledge(
                entities=[EntityNode(**e) for e in data.get("entities", [])],
                relations=[RelatedToRel(**r) for r in data.get("relations", [])],
            )
        except json.JSONDecodeError:
            logger.error(
                f"[GraphMemory] 摘要提取过程中发生 JSON 解析错误。原始文本: {raw_text}"
            )
            return None
        except Exception as e:
            logger.error(f"[GraphMemory] 从摘要中提取知识时出错: {e}", exc_info=True)
            return None

    def _find_json_blob(self, text: str) -> str | None:
        """
        从可能包含 Markdown 代码块或其他无关文本的字符串中稳健地找到 JSON 对象。
        例如，LLM 可能返回 ` ```json\n{...}\n``` `。
        """
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            return text[start : end + 1]
        return None

    async def rewrite_query(
        self, query: str, history: str, provider_id: str | None = None
    ) -> str:
        """
        结合对话历史，将用户的当前查询重写为一个独立的、无歧义的查询。
        这对于提高后续向量检索的准确性至关重要。

        Args:
            query (str):用户的原始查询。
            history (str): 最近的对话历史。
            provider_id (str | None): 用于此任务的 LLM Provider ID。如果为 None，则使用默认值。

        Returns:
            str: 重写后的查询。如果失败，则返回原始查询。
        """
        if not history:
            return query

        prompt = QUERY_REWRITING_PROMPT.format(history=history, query=query)

        effective_provider_id = provider_id or self.llm_provider_id
        if not effective_provider_id:
            logger.warning(
                "[GraphMemory] 没有可用的 provider 进行查询重写。返回原始查询。"
            )
            return query

        try:
            resp = await self.context.llm_generate(
                chat_provider_id=effective_provider_id, prompt=prompt
            )
            if resp and resp.completion_text:
                rewritten = resp.completion_text.strip()
                logger.debug(f"[GraphMemory] 重写查询: {rewritten}")
                return rewritten
        except Exception as e:
            logger.error(f"[GraphMemory] 查询重写错误: {e}")

        return query

    async def summarize(
        self, text_block: str, provider_id: str | None = None
    ) -> str | None:
        """
        将一个长文本块（通常是多轮对话）总结为一段简短的记忆摘要。
        这用于记忆巩固过程。

        Args:
            text_block (str): 要总结的文本。
            provider_id (str | None): 用于此任务的 LLM Provider ID。如果为 None，则使用默认值。

        Returns:
            str | None: 生成的摘要文本，如果失败则为 None。
        """
        prompt = SUMMARIZATION_PROMPT.format(text=text_block)

        effective_provider_id = provider_id or self.llm_provider_id
        if not effective_provider_id:
            logger.warning("[GraphMemory] 没有可用的 provider 进行摘要。跳过。")
            return None

        try:
            resp = await self.context.llm_generate(
                chat_provider_id=effective_provider_id, prompt=prompt
            )
            if resp and resp.completion_text:
                summary = resp.completion_text.strip()
                logger.debug(f"[GraphMemory] 生成的摘要: {summary[:100]}...")
                return summary
        except Exception as e:
            logger.error(f"[GraphMemory] 摘要生成错误: {e}")

        return None

    async def compress_memory(
        self, previous_summary: str, new_events: str, provider_id: str | None = None
    ) -> str | None:
        """
        将旧的摘要和新的对话事件压缩成一个新的摘要。

        Args:
            previous_summary (str): 上一个记忆片段的文本。
            new_events (str): 新的原始对话文本块。
            provider_id (str | None): 用于此任务的 LLM Provider ID。

        Returns:
            str | None: 生成的新的摘要文本，如果失败则为 None。
        """
        prompt = MEMORY_COMPRESSION_PROMPT.format(
            previous_summary=previous_summary, new_events=new_events
        )

        effective_provider_id = (
            provider_id or self.llm_provider_id
        )  # Fallback to main llm
        if not effective_provider_id:
            logger.warning("[GraphMemory] 没有可用的 provider 进行记忆压缩。")
            return None

        try:
            resp = await self.context.llm_generate(
                chat_provider_id=effective_provider_id, prompt=prompt
            )
            if resp and resp.completion_text:
                new_summary = resp.completion_text.strip()
                logger.debug(f"[GraphMemory] 生成的压缩记忆: {new_summary[:100]}...")
                return new_summary
        except Exception as e:
            logger.error(f"[GraphMemory] 记忆压缩错误: {e}", exc_info=True)

        return None

    async def summarize_to_intermediate(
        self, text_block: str, provider_id: str | None = None
    ) -> str | None:
        """
        将对话历史总结为中期记忆（首次总结时使用）。

        Args:
            text_block (str): 要总结的对话文本。
            provider_id (str | None): 用于此任务的 LLM Provider ID。

        Returns:
            str | None: 生成的中期记忆摘要，如果失败则为 None。
        """
        if not text_block.strip():
            return None

        prompt = INTERMEDIATE_MEMORY_PROMPT.format(text=text_block)

        effective_provider_id = provider_id or self.llm_provider_id
        if not effective_provider_id:
            logger.warning("[GraphMemory] 没有可用的 provider 进行中期记忆总结。")
            return None

        try:
            resp = await self.context.llm_generate(
                chat_provider_id=effective_provider_id, prompt=prompt
            )
            if resp and resp.completion_text:
                summary = resp.completion_text.strip()
                logger.debug(f"[GraphMemory] 生成的中期记忆: {summary[:100]}...")
                return summary
        except Exception as e:
            logger.error(f"[GraphMemory] 中期记忆总结错误: {e}")

        return None
