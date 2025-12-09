import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

# ==================== 1. 修复导入路径 ====================
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# ==================== 2. Mock astrbot ====================
# 创建独立的 mock 模块以解决 'is not a package' 问题
mock_astrbot = MagicMock()
mock_api = MagicMock()
mock_core = MagicMock()

# 将顶层包注册到 sys.modules
sys.modules["astrbot"] = mock_astrbot
sys.modules["astrbot.api"] = mock_api
sys.modules["astrbot.core"] = mock_core

# 模拟 astrbot.api 的子模块
mock_api_event = MagicMock()
mock_api_provider = MagicMock()
mock_api_star = MagicMock()
mock_api_message_components = MagicMock()
sys.modules["astrbot.api.event"] = mock_api_event
sys.modules["astrbot.api.provider"] = mock_api_provider
sys.modules["astrbot.api.star"] = mock_api_star
sys.modules["astrbot.api.message_components"] = mock_api_message_components

# 模拟 astrbot.core 的子模块
mock_core_message = MagicMock()
mock_core_message_event_result = MagicMock()
sys.modules["astrbot.core.message"] = mock_core_message
sys.modules["astrbot.core.message.message_event_result"] = (
    mock_core_message_event_result
)

# 在 mock 模块上设置预期的属性
mock_api.logger = MagicMock()
mock_api_event.AstrMessageEvent = MagicMock()
mock_api_provider.LLMResponse = MagicMock()
mock_api_provider.ProviderRequest = MagicMock()
mock_api_star.Context = MagicMock()
mock_core_message_event_result.MessageEventResult = MagicMock()

# ==================== 3. 导入业务代码 ====================
from core.extractor import ExtractedData, KnowledgeExtractor  # noqa: E402
from core.prompts import QUERY_REWRITING_PROMPT, SUMMARIZATION_PROMPT  # noqa: E402

# ==================== 4. 测试 Fixtures ====================


@pytest.fixture
def mock_context():
    """提供一个 mock 的 AstrBot Context 对象。"""
    context = MagicMock()
    context.get_current_chat_provider_id = AsyncMock(return_value="test_provider")
    context.llm_generate = AsyncMock()
    return context


@pytest.fixture
def extractor(mock_context):
    """提供一个 KnowledgeExtractor 实例。"""
    return KnowledgeExtractor(
        context=mock_context,
        llm_provider_id="default_provider",
        embedding_provider=None,
    )


# ==================== 5. 测试用例 ====================


@pytest.mark.asyncio
async def test_extract_success(extractor, mock_context):
    """测试：成功从文本中提取结构化数据。"""
    # 准备
    text_block = "用户A: 你好. Bot: 你好，有什么可以帮忙的？"
    session_id = "test_session"
    mock_response = {
        "users": [{"id": "user_a", "name": "用户A", "platform": "test"}],
        "entities": [{"name": "你好", "type": "Greeting"}],
        "relations": [],
        "mentions": [],
        "messages": [],
        "sessions": [],
    }
    mock_llm_resp = MagicMock()
    mock_llm_resp.completion_text = json.dumps(mock_response)
    mock_context.llm_generate.return_value = mock_llm_resp

    # 执行
    result = await extractor.extract(text_block, session_id)

    # 验证
    assert isinstance(result, ExtractedData)
    assert len(result.users) == 1
    assert result.users[0].name == "用户A"
    assert len(result.entities) == 1
    assert result.entities[0].name == "你好"
    mock_context.llm_generate.assert_called_once()


@pytest.mark.asyncio
async def test_extract_with_markdown(extractor, mock_context):
    """测试：LLM 响应被 Markdown 代码块包裹时也能正确解析。"""
    # 准备
    text_block = "用户B: 晚安"
    session_id = "test_session_2"
    mock_response = {"entities": [{"name": "晚安", "type": "Farewell"}]}
    mock_llm_resp = MagicMock()
    mock_llm_resp.completion_text = f"```json\n{json.dumps(mock_response)}\n```"
    mock_context.llm_generate.return_value = mock_llm_resp

    # 执行
    result = await extractor.extract(text_block, session_id)

    # 验证
    assert result is not None
    assert len(result.entities) == 1
    assert result.entities[0].name == "晚安"


@pytest.mark.asyncio
async def test_extract_empty_or_invalid_json(extractor, mock_context):
    """测试：LLM 返回空响应或无效 JSON 时，应返回 None。"""
    # 准备
    text_block = "一些无关紧要的文本"
    session_id = "test_session_3"

    # 场景 1: 空响应
    mock_context.llm_generate.return_value = None
    result1 = await extractor.extract(text_block, session_id)
    assert result1 is None

    # 场景 2: 无效 JSON
    mock_llm_resp = MagicMock()
    mock_llm_resp.completion_text = "这不是一个JSON"
    mock_context.llm_generate.return_value = mock_llm_resp
    result2 = await extractor.extract(text_block, session_id)
    assert result2 is None


@pytest.mark.asyncio
async def test_rewrite_query(extractor, mock_context):
    """测试：查询重写功能。"""
    # 准备
    query = "它怎么样？"
    history = (
        "用户A: 我想了解一下关于 AstrBot 的信息。\nBot: 好的，AstrBot 是一个开源项目。"
    )
    rewritten_query = "AstrBot 怎么样？"

    mock_llm_resp = MagicMock()
    mock_llm_resp.completion_text = rewritten_query
    mock_context.llm_generate.return_value = mock_llm_resp

    # 执行
    result = await extractor.rewrite_query(query, history)

    # 验证
    assert result == rewritten_query
    expected_prompt = QUERY_REWRITING_PROMPT.format(history=history, query=query)
    mock_context.llm_generate.assert_called_with(
        chat_provider_id="default_provider", prompt=expected_prompt
    )


@pytest.mark.asyncio
async def test_summarize(extractor, mock_context):
    """测试：文本摘要功能。"""
    # 准备
    text_block = "这是一段非常非常长的对话历史..."
    summary = "对话核心是关于..."

    mock_llm_resp = MagicMock()
    mock_llm_resp.completion_text = summary
    mock_context.llm_generate.return_value = mock_llm_resp

    # 执行
    result = await extractor.summarize(text_block)

    # 验证
    assert result == summary
    expected_prompt = SUMMARIZATION_PROMPT.format(text=text_block)
    mock_context.llm_generate.assert_called_with(
        chat_provider_id="default_provider", prompt=expected_prompt
    )


@pytest.mark.asyncio
async def test_extract_no_provider(extractor, mock_context):
    """测试：在没有可用 LLM Provider 时，提取操作应失败。"""
    # 准备
    extractor.llm_provider_id = None
    mock_context.get_current_chat_provider_id.return_value = None

    # 执行
    result = await extractor.extract("一些文本", "some_session")

    # 验证
    assert result is None
    mock_context.llm_generate.assert_not_called()
