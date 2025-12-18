import apiClient from './client'

export const relationApi = {
  // 获取关系列表
  list: (params?: any) =>
    apiClient.get<any, any>('/relations', { params }),

  // 删除关系
  delete: (from: string, to: string) =>
    apiClient.delete<any, any>('/relations', {
      params: { from_entity: from, to_entity: to },
    }),
}
