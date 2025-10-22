// API 类型定义
export interface CreateKnowledgeBaseRequest {
  name: string;
  description?: string;
  parser_id?: string;
  parser_config?: Record<string, any>;
  embd_id?: string;
}

export interface UpdateKnowledgeBaseRequest {
  kb_id: string;
  name: string;
  pagerank?: number;
}

export interface DeleteKnowledgeBaseRequest {
  kb_id: string;
}

export interface GetKnowledgeBaseRequest {
  kb_id: string;
}

export interface ListKnowledgeBasesRequest {
  owner_ids?: string[];
}

export interface KnowledgeBase {
  id: string;
  name: string;
  description?: string;
  parser_id: string;
  parser_config?: Record<string, any>;
  embd_id?: string;
  create_time: string;
  update_time: string;
  tenant_id: string;
  status: string;
  chunk_count: number;
  document_count: number;
  tags?: string[];
}

export interface ApiResponse<T = any> {
  code: number;
  data?: T;
  message: string;
  headers?: {
    authorization?: string;
    Authorization?: string;
    [key: string]: any;
  };
}

export interface ListResponse<T> {
  kbs: T[];
  total: number;
}

// 登录相关类型
export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  authorization: string;
  user?: {
    id: string;
    email: string;
    name?: string;
  };
}
