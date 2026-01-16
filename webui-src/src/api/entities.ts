import apiClient from './client'

export interface Entity {
  name: string
  type: string
  description: string
  importance: number
  access_count: number
  created_at: string
  last_accessed: string
}

export const entityApi = {
  // 获取实体列表
  list: (params?: any) =>
    apiClient.get<any, any>('/entities', { params }),

  // 获取单个实体
  get: (name: string) =>
    apiClient.get<any, any>(`/entities/${name}`),

  // 删除实体
  delete: (name: string, params?: any) =>
    apiClient.delete<any, any>(`/entities/${name}`, { params }),
}
