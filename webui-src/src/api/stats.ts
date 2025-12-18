import apiClient from './client'

export const statsApi = {
  // 获取统计概览
  getOverview: () =>
    apiClient.get<any, any>('/stats/overview'),

  // 获取实体类型分布
  getEntityTypes: () =>
    apiClient.get<any, any>('/stats/entity-types'),

  // 获取时间线统计
  getTimeline: () =>
    apiClient.get<any, any>('/stats/timeline'),
}
