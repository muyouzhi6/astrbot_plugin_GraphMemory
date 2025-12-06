# data/plugins/astrbot_plugin_GraphMemory/core/prompts.py

"""
此文件集中管理了所有用于与大语言模型（LLM）交互的提示（Prompts）。
将提示与业务逻辑代码分离，使得修改和优化提示变得更加容易，而无需改动核心代码。
"""

# --- 知识提取提示 (Knowledge Extraction Prompt) ---

EXTRACTION_PROMPT = """
你是一个超级智能的知识图谱分析师。你的任务是分析一段对话，并从中提取结构化信息。

**输入对话:**
```
{text}
```

**指令:**
1.  **识别核心实体**: 提取提到的关键人物、地点、概念或事件。对它们进行归一化处理（例如："JS" -> "JavaScript"）。
2.  **提取关系**: 寻找实体之间明确的关系（例如："用户A喜欢Python"，"公司X开发了产品Y"）。
3.  **识别说话者和上下文**: 对于每一条信息，识别出说话者（`UserNode`）和对话上下文（`SessionNode`）。
4.  **输出JSON**: 将所有提取的信息格式化为一个单一的JSON对象，其结构如下。不要输出任何其他内容。如果没有发现有价值的信息，返回一个空的JSON对象 {{}}。

**输出JSON结构:**
```json
{{
  "users": [
    {{
      "id": "platform_user_id",
      "name": "nickname",
      "platform": "e.g., qq"
    }}
  ],
  "sessions": [
    {{
      "id": "platform_group_or_private_id",
      "type": "GROUP or PRIVATE",
      "name": "group_name"
    }}
  ],
  "messages": [
    {{
      "id": "message_id",
      "content": "Original message text...",
      "timestamp": 1678886400,
      "sender_id": "platform_user_id",
      "session_id": "platform_group_or_private_id"
    }}
  ],
  "entities": [
    {{
      "name": "Normalized Entity Name",
      "type": "Concept, Person, Location, etc."
    }}
  ],
  "relations": [
    {{
      "src_entity": "Entity1 Name",
      "tgt_entity": "Entity2 Name",
      "relation": "IS_A"
    }}
  ],
  "mentions": [
    {{
      "message_id": "message_id",
      "entity_name": "Entity Name",
      "sentiment": "Positive, Negative, or Neutral"
    }}
  ]
}}
```
"""

# --- 查询重写提示 (Query Rewriting Prompt) ---

QUERY_REWRITING_PROMPT = """
根据最近的对话历史和用户的最新查询，将该查询重写为一个独立的、自包含的问题。
这有助于消除代词和上下文依赖，以便进行更准确的向量搜索。

**对话历史:**
{history}

**用户的查询:** "{query}"

**重写后的查询:**
"""

# --- 摘要生成提示 (Summarization Prompt) ---

SUMMARIZATION_PROMPT = """
你是一位专业的摘要员。请根据以下的对话记录，以第三人称的视角，创建一个简洁的摘要，总结其中关键的事件、事实和用户观点。

**对话记录:**
```
{text}
```

**指令:**
- 专注于长期相关的信息。
- 忽略闲聊和问候语。
- 摘要应该是一个独立的段落。

**摘要:**
"""
