# FastAPI Migration: api_utils.py

## 概述
已将 `api/utils/api_utils.py` 从 Flask 迁移到 FastAPI，移除了所有 Flask 依赖。

## 主要变更

### 1. 导入变更
**移除的 Flask 导入：**
```python
from flask import Response, jsonify, make_response, send_file
from flask_login import current_user
from flask import request as flask_request
```

**新增的 FastAPI 导入：**
```python
from fastapi import Request, Response as FastAPIResponse, HTTPException, status
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
```

### 2. 装饰器迁移
以下 Flask 装饰器已被标记为废弃，保留是为了向后兼容：

- `validate_request()` - 在 FastAPI 中使用 Pydantic 模型进行验证
- `not_allowed_parameters()` - 在 FastAPI 中使用 Pydantic 模型进行验证
- `active_required()` - 在 FastAPI 中使用依赖注入进行用户验证
- `apikey_required()` - 在 FastAPI 中使用依赖注入进行 API Key 验证
- `token_required()` - 在 FastAPI 中使用依赖注入进行 Token 验证

### 3. 新增 FastAPI 依赖注入函数

#### `get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security))`
- 替代 Flask 的 `current_user`
- 使用 JWT token 验证用户身份
- 返回用户对象或抛出 HTTPException

#### `get_current_user_optional(credentials: HTTPAuthorizationCredentials = Depends(security))`
- 可选版本的用户验证
- 验证失败时返回 None 而不是抛出异常

#### `verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security))`
- 替代 `apikey_required` 装饰器
- 验证 API Key 并返回 APIToken 对象

#### `create_file_response(data, filename: str, media_type: str = "application/octet-stream")`
- 替代 Flask 的 `send_file`
- 使用 FastAPI 的 `StreamingResponse` 返回文件

### 4. 响应函数更新
所有响应函数已更新为使用 FastAPI 的 `JSONResponse`：

- `get_json_result()` → `JSONResponse`
- `construct_response()` → `JSONResponse`
- `get_data_error_result()` → `JSONResponse`
- `build_error_result()` → `JSONResponse`
- `construct_result()` → `JSONResponse`
- `construct_json_result()` → `JSONResponse`
- `get_result()` → `JSONResponse`
- `get_error_data_result()` → `JSONResponse`
- `error_response()` → `JSONResponse`

### 5. 文件处理更新
- `send_file_in_mem()` 现在返回文件对象，调用者需要处理响应
- 新增 `create_file_response()` 用于创建文件响应

## 使用示例

### 旧版本 (Flask)
```python
@manager.route("/login", methods=["POST"])
@validate_request("email", "password")
@login_required
def login():
    req = request.get_json()
    # 处理登录逻辑
    return get_json_result(data=user_data)
```

### 新版本 (FastAPI)
```python
@router.post("/login")
async def login(
    request: LoginRequest,
    current_user: User = Depends(get_current_user)
):
    # 处理登录逻辑
    return get_json_result(data=user_data)
```

## 迁移指南

1. **路由定义**：从 Flask 的 `@manager.route()` 迁移到 FastAPI 的 `@router.post()` 等
2. **请求验证**：从 `@validate_request()` 迁移到 Pydantic 模型
3. **用户认证**：从 `@login_required` 迁移到 `Depends(get_current_user)`
4. **API Key 验证**：从 `@apikey_required` 迁移到 `Depends(verify_api_key)`
5. **文件响应**：从 `send_file()` 迁移到 `create_file_response()`

## 注意事项

- 所有旧的装饰器函数保留是为了向后兼容，但不会执行任何验证
- 新的依赖注入函数是异步的，需要使用 `async/await`
- FastAPI 会自动验证 Pydantic 模型，无需手动验证
- 错误处理使用 `HTTPException` 而不是返回错误响应

## 兼容性

- 保持与现有代码的向后兼容性
- 所有响应格式保持一致
- 错误代码和消息格式不变
