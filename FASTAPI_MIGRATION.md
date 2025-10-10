# RAGFlow FastAPI 迁移说明

## 概述

本文档描述了将 RAGFlow 从 Flask 框架迁移到 FastAPI 框架的过程。迁移是逐步进行的，首先迁移核心服务器文件和用户应用。

## 迁移的文件

### 1. 核心服务器文件
- **原文件**: `api/ragflow_server.py` (Flask版本)
- **新文件**: `api/ragflow_server_fastapi.py` (FastAPI版本)

### 2. 用户应用文件
- **原文件**: `api/apps/user_app.py` (Flask版本)
- **新文件**: `api/apps/user_app_fastapi.py` (FastAPI版本)

### 3. 应用初始化文件
- **原文件**: `api/apps/__init__.py` (Flask版本)
- **新文件**: `api/apps/__init___fastapi.py` (FastAPI版本)

## 主要变化

### 1. 框架替换
- **Flask** → **FastAPI**
- **Flask-Login** → **FastAPI 依赖注入系统**
- **Flasgger** → **FastAPI 内置 OpenAPI 文档**
- **Flask-CORS** → **FastAPI CORS 中间件**

### 2. 路由系统
- **Flask Blueprint** → **FastAPI APIRouter**
- **Flask 装饰器** → **FastAPI 依赖注入**

### 3. 请求处理
- **Flask request** → **FastAPI Request 对象**
- **Flask session** → **FastAPI Session 中间件**

### 4. 响应处理
- **Flask Response** → **FastAPI Response 类**
- **Flask redirect** → **FastAPI RedirectResponse**

### 5. 数据验证
- **手动验证** → **Pydantic 模型验证**

## 使用方法

### 启动 FastAPI 服务器

```bash
python api/ragflow_server_fastapi.py
```

### 访问 API 文档

- **Swagger UI**: `http://localhost:8000/apidocs/`
- **ReDoc**: `http://localhost:8000/redoc/`
- **OpenAPI JSON**: `http://localhost:8000/apispec.json`

## 主要特性

### 1. 自动 API 文档
FastAPI 自动生成交互式 API 文档，无需额外配置。

### 2. 类型安全
使用 Pydantic 模型提供数据验证和类型检查。

### 3. 异步支持
FastAPI 原生支持异步操作，提供更好的性能。

### 4. 依赖注入
使用 FastAPI 的依赖注入系统处理身份验证和授权。

## 注意事项

### 1. 会话管理
FastAPI 的会话管理与 Flask 略有不同，需要适配。

### 2. 中间件
FastAPI 的中间件系统与 Flask 不同，需要重新实现。

### 3. 错误处理
FastAPI 的异常处理机制需要适配。

### 4. 数据库连接
需要确保数据库连接在请求结束时正确关闭。

## 后续工作

1. 迁移其他应用文件（canvas_app.py, document_app.py 等）
2. 测试所有 API 端点
3. 性能优化
4. 文档更新
5. 部署配置更新

## 依赖项

确保安装以下 FastAPI 相关依赖：

```bash
pip install fastapi uvicorn python-multipart
```

## 故障排除

### 常见问题

1. **导入错误**: 确保所有模块路径正确
2. **依赖注入错误**: 检查依赖项配置
3. **中间件错误**: 确保中间件顺序正确
4. **数据库连接**: 检查数据库连接配置

### 调试

使用以下命令启动调试模式：

```bash
python api/ragflow_server_fastapi.py --debug
```

## 联系信息

如有问题，请联系开发团队。
