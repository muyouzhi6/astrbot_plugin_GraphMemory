import apiClient from './client'

export const systemApi = {
  // 获取系统状态
  getStatus: () =>
    apiClient.get<any, any>('/system/status'),

  // 导出图谱
  export: (params?: any) =>
    apiClient.get<any, any>('/system/export', { params }),

  // 导入图谱
  import: (data: { content: string; merge: boolean }) =>
    apiClient.post<any, any>('/system/import', data),

  // 清理图谱
  cleanup: (params: { action: string; threshold?: number }) =>
    apiClient.post<any, any>('/system/cleanup', null, { params }),
}
