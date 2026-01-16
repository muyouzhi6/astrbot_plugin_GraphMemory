import apiClient from './client'

export interface SearchRequest {
  query: string
  session_id?: string
  top_k?: number
  include_evidence?: boolean
}

export const searchApi = {
  // 混合搜索
  hybrid: (data: SearchRequest) =>
    apiClient.post<any, any>('/search/hybrid', data),

  // 向量搜索
  vector: (data: SearchRequest) =>
    apiClient.post<any, any>('/search/vector', data),

  // 关键词搜索
  keyword: (data: SearchRequest) =>
    apiClient.post<any, any>('/search/keyword', data),
}
