/**
 * API服务模块
 * 
 * 统一管理所有HTTP请求的配置和拦截器
 * - 所有请求头（Content-Type、Authorization等）在请求拦截器中统一设置
 * - 避免在每个接口调用中重复设置headers
 * - 提供统一的错误处理和token管理
 */

import axios from 'axios';
import { message } from 'antd';
import type {
  CreateKnowledgeBaseRequest,
  UpdateKnowledgeBaseRequest,
  DeleteKnowledgeBaseRequest,
  GetKnowledgeBaseRequest,
  ListKnowledgeBasesRequest,
  LoginRequest,
  LoginResponse,
  KnowledgeBase,
  ApiResponse,
  ListResponse
} from '../types/api';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://192.168.0.118:9380';

// 创建axios实例，统一配置基础设置
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  // 默认请求头设置（会被请求拦截器覆盖以确保一致性）
  headers: {
    'Content-Type': 'application/json;charset=UTF-8',
  },
  // 确保请求数据被正确序列化
  transformRequest: [(data: any) => {
    // 处理undefined和null
    if (data === undefined || data === null) {
      return JSON.stringify({});
    }
    
    // 处理对象
    if (typeof data === 'object') {
      return JSON.stringify(data);
    }
    
    // 处理字符串
    if (typeof data === 'string') {
      return data;
    }
    
    // 其他类型转换为字符串
    return String(data);
  }],
});

// Token 管理
const TOKEN_KEY = 'authorization';

export const tokenManager = {
  // 获取token
  getToken: (): string | null => {
    return localStorage.getItem(TOKEN_KEY);
  },
  
  // 设置token
  setToken: (token: string): void => {
    localStorage.setItem(TOKEN_KEY, token);
  },
  
  // 清除token
  clearToken: (): void => {
    localStorage.removeItem(TOKEN_KEY);
  },
  
  // 检查是否已登录
  isLoggedIn: (): boolean => {
    return !!tokenManager.getToken();
  }
};

// 请求拦截器 - 统一管理请求头
api.interceptors.request.use(
  (config: any) => {
    const token = tokenManager.getToken();
    
    // 确保headers对象存在
    if (!config.headers) {
      config.headers = {};
    }
    
    // 统一设置Content-Type（覆盖任何现有的设置）
    config.headers['Content-Type'] = 'application/json;charset=UTF-8';
    
    // 添加认证token（如果存在）
    if (token) {
      config.headers.Authorization = `${token}`;
    }
    
    return config;
  },
  (error: any) => {
    return Promise.reject(error);
  }
);

// 全局导航管理器
let globalNavigate: ((path: string) => void) | null = null;

export const setGlobalNavigate = (navigate: (path: string) => void) => {
  globalNavigate = navigate;
};

// 响应拦截器
api.interceptors.response.use(
  (response: any) => {
    // 检查业务层面的401错误码
    if (response.data?.code === 401 || response.data?.code === 403) {
      // 显示用户友好的提示信息
      if (response.data.code === 401) {
        message.warning('登录已过期，请重新登录');
      } else {
        message.warning('访问被拒绝，请重新登录');
      }
      
      // 清除token
      tokenManager.clearToken();
      
      // 延迟执行跳转，确保message显示完成
      setTimeout(() => {
        if (window.location.pathname !== '/login') {
          window.location.href = '/login';
        }
      }, 500);
      
      // 返回一个被拒绝的Promise，模拟错误
      return Promise.reject({
        response: {
          status: response.data.code,
          data: response.data
        }
      });
    }
    
    // 保留响应头信息，将data和headers都返回
    return {
      ...response.data,
      headers: response.headers
    };
  },
  (error: any) => {
    // 处理HTTP层面的401未授权和403禁止访问
    if (error.response?.status === 401 || error.response?.status === 403) {
      // 显示用户友好的提示信息
      if (error.response?.status === 401) {
        message.warning('登录已过期，请重新登录');
      } else {
        message.warning('访问被拒绝，请重新登录');
      }
      
      // 清除token
      tokenManager.clearToken();
      
      // 延迟执行跳转，确保message显示完成
      setTimeout(() => {
        if (window.location.pathname !== '/login') {
          window.location.href = '/login';
        }
      }, 500);
    }
    
    return Promise.reject(error);
  }
);

// 认证API
export const authApi = {
  // 用户登录
  login: async (data: LoginRequest): Promise<ApiResponse<LoginResponse>> => {
    return api.post('/v1/user/login', data);
  },
  
  // 用户登出
  logout: async (): Promise<void> => {
    tokenManager.clearToken();
  },
};

export const knowledgeBaseApi = {
  // 创建知识库
  create: async (data: CreateKnowledgeBaseRequest): Promise<ApiResponse<KnowledgeBase>> => {
    return api.post('/v1/kb/create', data);
  },

  // 更新知识库
  update: async (data: UpdateKnowledgeBaseRequest): Promise<ApiResponse<KnowledgeBase>> => {
    return api.post('/v1/kb/update', data);
  },

  // 删除知识库
  delete: async (data: DeleteKnowledgeBaseRequest): Promise<ApiResponse> => {
    return api.post('/v1/kb/delete', data);
  },

  // 获取知识库列表
  list: async (data?: ListKnowledgeBasesRequest): Promise<ApiResponse<ListResponse<KnowledgeBase>>> => {
    // 确保data不为undefined，即使是空对象也要传递
    const requestData = data || {};
    return api.post('/v1/kb/list', requestData);
  },

  // 获取知识库详情
  get: async (data: GetKnowledgeBaseRequest): Promise<ApiResponse<KnowledgeBase>> => {
    return api.post(`/v1/kb/${data.kb_id}`, data);
  },
};

export default api;
