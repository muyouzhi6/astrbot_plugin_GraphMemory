"""通用数据模型"""

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """API 响应格式"""

    success: bool
    data: T | None = None
    error: str | None = None
    message: str | None = None


class EntityNode(BaseModel):
    """实体节点"""

    name: str
    type: str
    description: str
    importance: float
    access_count: int
    created_at: str
    last_accessed: str


class RelationEdge(BaseModel):
    """关系边"""

    from_entity: str
    to_entity: str
    relation: str
    strength: float
    evidence: str
    created_at: str
    last_updated: str
