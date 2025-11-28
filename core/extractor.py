import json
from dataclasses import dataclass

from astrbot.api import logger
from astrbot.api.star import Context

from .prompts import GROUP_CHAT_PROMPT, PRIVATE_CHAT_PROMPT, SEARCH_KEYWORDS_PROMPT


@dataclass
class Triplet:
    src: str
    rel: str
    tgt: str
    src_type: str = "entity"
    tgt_type: str = "entity"
    weight: float = 1.0
    confidence: float = 1.0
    source_user: str = "unknown"  # Who provided this info


class KnowledgeExtractor:
    def __init__(self, context: Context, provider_id: str | None = None):
        self.context = context
        self.provider_id = provider_id

    async def extract(self, text_block: str, is_group: bool = False) -> list[Triplet]:
        """
        从文本块中提取三元组
        """
        if not text_block.strip():
            return []

        if is_group:
            prompt = GROUP_CHAT_PROMPT.format(text=text_block)
        else:
            prompt = PRIVATE_CHAT_PROMPT.format(text=text_block)

        return await self._call_llm(prompt)

    async def _call_llm(self, prompt: str) -> list[Triplet]:
        """
        调用 LLM 并解析 JSON
        """
        try:
            # 如果没有指定 provider_id，则需要从外部传入或获取默认。
            # 这里我们假定调用方保证 provider_id 有效，或者我们尝试获取默认
            # 注意：context.llm_generate 在 v4.5.7+ 可用

            # 使用新的 llm_generate 接口
            # 注意：如果 self.provider_id 为 None，可能需要 fallback 策略
            # 这里我们假设在 main.py 初始化时会传入一个可用的 provider_id (例如从配置获取)

            if not self.provider_id:
                logger.warning(
                    "[GraphMemory] No provider_id configured for extraction."
                )
                return []

            resp = await self.context.llm_generate(
                chat_provider_id=self.provider_id, prompt=prompt
            )

            if not resp or not resp.completion_text:
                return []

            raw_text = resp.completion_text

            # 简单的 JSON 提取逻辑
            # 尝试找到第一个 [ 和最后一个 ]
            start = raw_text.find("[")
            end = raw_text.rfind("]")

            if start == -1 or end == -1:
                return []

            json_str = raw_text[start : end + 1]
            data = json.loads(json_str)

            triplets = []
            for item in data:
                triplets.append(
                    Triplet(
                        src=item.get("src", ""),
                        rel=item.get("rel", ""),
                        tgt=item.get("tgt", ""),
                        confidence=item.get("confidence", 1.0),
                        source_user=item.get("source_user", "unknown"),
                    )
                )

            return triplets

        except json.JSONDecodeError:
            logger.error("[GraphMemory] Failed to parse JSON from LLM response.")
            return []
        except Exception as e:
            logger.error(f"[GraphMemory] LLM extraction error: {e}")
            return []

    async def extract_keywords(self, query: str) -> list[str]:
        """
        提取搜索关键词
        """
        if not self.provider_id:
            return []

        prompt = SEARCH_KEYWORDS_PROMPT.format(query=query)

        try:
            resp = await self.context.llm_generate(
                chat_provider_id=self.provider_id, prompt=prompt
            )
            if resp and resp.completion_text:
                text = resp.completion_text.strip()
                # 移除可能的 markdown 代码块
                text = text.replace("```", "").strip()
                keywords = [k.strip() for k in text.split(",") if k.strip()]
                return keywords
        except Exception as e:
            logger.error(f"[GraphMemory] Keyword extraction error: {e}")

        return []
