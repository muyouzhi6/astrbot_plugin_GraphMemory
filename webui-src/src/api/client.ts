import axios from 'axios'

const apiClient = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// 请求拦截器 - 添加访问密钥
apiClient.interceptors.request.use((config) => {
  const key = localStorage.getItem('webui_key')
  if (key) {
    config.params = {
      ...config.params,
      key,
    }
  }
  return config
})

// 响应拦截器 - 处理错误
apiClient.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response?.status === 401) {
      // 密钥无效，清除并跳转到登录页
      localStorage.removeItem('webui_key')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default apiClient
