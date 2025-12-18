import apiClient from './client'

export interface GraphNode {
  id: string
  label: string
  properties: Record<string, any>
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  label: string
  properties: Record<string, any>
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export const graphApi = {
  // 获取会话图谱
  getSessionGraph: (sessionId: string, params?: any) =>
    apiClient.get<any, any>(`/graph/session/${sessionId}`, { params }),

  // 获取全局图谱
  getGlobalGraph: (params?: any) =>
    apiClient.get<any, any>('/graph/global', { params }),

  // 获取实体邻居
  getNeighbors: (entityName: string, params?: any) =>
    apiClient.get<any, any>(`/graph/neighbors/${entityName}`, { params }),
}
