import axios, { AxiosInstance, InternalAxiosRequestConfig, AxiosResponse } from 'axios'
import { ElMessage } from 'element-plus'

/**
 * 动态检测 API 基础 URL
 * 当通过 /stock/ 前缀访问时，API 请求也需要带上前缀
 */
function getApiBaseURL(): string {
  if (window.location.pathname.startsWith('/stock')) {
    return '/stock/instock'
  }
  return '/instock'
}

// 创建 axios 实例
const service: AxiosInstance = axios.create({
  baseURL: getApiBaseURL(),
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json;charset=UTF-8'
  }
})

// 请求拦截器
service.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // 在发送请求之前做些什么
    return config
  },
  (error) => {
    console.error('请求错误:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器
service.interceptors.response.use(
  (response: AxiosResponse) => {
    return response.data
  },
  (error) => {
    console.error('响应错误:', error)
    const serverMsg = error?.response?.data?.error
    ElMessage.error(serverMsg || error.message || '网络错误')
    return Promise.reject(error)
  }
)

export default service
