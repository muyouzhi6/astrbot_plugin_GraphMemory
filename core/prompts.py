# 私聊提取提示词
PRIVATE_CHAT_PROMPT = """
You are a Knowledge Graph extraction system.
Analyze the following private chat history between a User and an AI Assistant.
Extract relevant information as a list of triplets (Source, Relation, Target).

Guidelines:
1. Focus on the User's profile (name, job, age, location), preferences (likes, dislikes), and life events.
2. Ignore simple chitchat (e.g., "Hello", "How are you").
3. Use concise and normalized names for entities (e.g., use "User" for the human speaker if name is unknown).
4. Confidence should be 1.0 for direct statements by the user.

Input Chat:
{text}

Output Format:
Return ONLY a JSON list of objects. No markdown formatting.
[
  {{
    "src": "Entity1",
    "rel": "relation",
    "tgt": "Entity2",
    "confidence": 1.0,
    "source_user": "user_id_or_name"
  }}
]
If no info, return [].
"""

# 群聊提取提示词
GROUP_CHAT_PROMPT = """
You are a Knowledge Graph extraction system.
Analyze the following GROUP CHAT history.
Extract relevant information as a list of triplets (Source, Relation, Target).

Guidelines:
1. Identify who is who. Extract user relationships (e.g., A is friend of B) and user characteristics.
2. Distinguish between FACTS (high confidence) and OPINIONS (lower confidence).
3. Ignore chitchat, memes, and noise. Focus on long-term relevant info.
4. "source_user" should be the name/ID of the speaker who provided the information.

Input Chat (Format: [role:name:id]: content):
{text}

Output Format:
Return ONLY a JSON list of objects. No markdown formatting.
[
  {{
    "src": "Entity1",
    "rel": "relation",
    "tgt": "Entity2",
    "confidence": 0.8,
    "source_user": "sender_name"
  }}
]
If no info, return [].
"""

# 搜索关键词提取提示词
SEARCH_KEYWORDS_PROMPT = """
Given the user query: "{query}"
Generate 2-4 search keywords to retrieve relevant memory from a knowledge graph.
Keywords should be entities or concepts.
Return ONLY a comma-separated list.
"""
