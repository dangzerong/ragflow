# FastAPI Migration: kb_app.py

## 概述
已将 `api/apps/kb_app.py` 从 Flask 迁移到 FastAPI，移除了所有 Flask 依赖。

## 主要变更

### 1. 导入变更
**移除的 Flask 导入：**
```python
from flask import request
from flask_login import login_required, current_user
```

**新增的 FastAPI 导入：**
```python
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from api.models.kb_models import (
    CreateKnowledgeBaseRequest,
    UpdateKnowledgeBaseRequest,
    DeleteKnowledgeBaseRequest,
    # ... 其他模型
)
from api.utils.api_utils import get_current_user
```

### 2. 创建 Pydantic 模型
新增 `api/models/kb_models.py` 文件，包含以下请求模型：

- `CreateKnowledgeBaseRequest` - 创建知识库
- `UpdateKnowledgeBaseRequest` - 更新知识库
- `DeleteKnowledgeBaseRequest` - 删除知识库
- `ListKnowledgeBasesRequest` - 列出知识库
- `RemoveTagsRequest` - 移除标签
- `RenameTagRequest` - 重命名标签
- `RunGraphRAGRequest` - 运行GraphRAG
- `RunRaptorRequest` - 运行RAPTOR
- `RunMindmapRequest` - 运行Mindmap
- `ListPipelineLogsRequest` - 列出管道日志
- `ListPipelineDatasetLogsRequest` - 列出管道数据集日志
- `DeletePipelineLogsRequest` - 删除管道日志
- `UnbindTaskRequest` - 解绑任务

### 3. 路由迁移
所有 Flask 路由已迁移到 FastAPI：

#### 知识库管理
- `POST /create` - 创建知识库
- `POST /update` - 更新知识库
- `GET /detail` - 获取知识库详情
- `POST /list` - 列出知识库
- `POST /rm` - 删除知识库

#### 标签管理
- `GET /{kb_id}/tags` - 获取知识库标签
- `GET /tags` - 获取多个知识库标签
- `POST /{kb_id}/rm_tags` - 移除标签
- `POST /{kb_id}/rename_tag` - 重命名标签

#### 知识图谱
- `GET /{kb_id}/knowledge_graph` - 获取知识图谱
- `DELETE /{kb_id}/knowledge_graph` - 删除知识图谱

#### 元数据
- `GET /get_meta` - 获取元数据
- `GET /basic_info` - 获取基本信息

#### 管道日志
- `POST /list_pipeline_logs` - 列出管道日志
- `POST /list_pipeline_dataset_logs` - 列出管道数据集日志
- `POST /delete_pipeline_logs` - 删除管道日志
- `GET /pipeline_log_detail` - 获取管道日志详情

#### 任务管理
- `POST /run_graphrag` - 运行GraphRAG
- `GET /trace_graphrag` - 跟踪GraphRAG任务
- `POST /run_raptor` - 运行RAPTOR
- `GET /trace_raptor` - 跟踪RAPTOR任务
- `POST /run_mindmap` - 运行Mindmap
- `GET /trace_mindmap` - 跟踪Mindmap任务
- `DELETE /unbind_task` - 解绑任务

### 4. 装饰器迁移
**Flask 装饰器 → FastAPI 依赖注入：**

```python
# 旧版本 (Flask)
@login_required
@validate_request("kb_id", "name")
def update():
    req = request.json
    # ...

# 新版本 (FastAPI)
@router.post('/update')
async def update(
    request: UpdateKnowledgeBaseRequest,
    current_user = Depends(get_current_user)
):
    # ...
```

### 5. 请求处理更新
**参数获取方式变更：**

```python
# 旧版本 (Flask)
kb_id = request.args["kb_id"]
keywords = request.args.get("keywords", "")
req = request.get_json()

# 新版本 (FastAPI)
@router.get('/detail')
async def detail(
    kb_id: str = Query(..., description="知识库ID"),
    keywords: str = Query("", description="关键词"),
    current_user = Depends(get_current_user)
):
```

### 6. 响应格式
所有响应继续使用 `get_json_result()` 函数，保持与现有 API 的兼容性。

## 使用示例

### 创建知识库
```python
# 请求
POST /create
{
    "name": "我的知识库",
    "description": "这是一个测试知识库",
    "parser_id": "naive"
}

# 响应
{
    "code": 0,
    "data": {
        "kb_id": "uuid-string"
    }
}
```

### 获取知识库详情
```python
# 请求
GET /detail?kb_id=uuid-string

# 响应
{
    "code": 0,
    "data": {
        "id": "uuid-string",
        "name": "我的知识库",
        "description": "这是一个测试知识库",
        "size": 1024
    }
}
```

## 迁移指南

1. **路由定义**：从 `@manager.route()` 迁移到 `@router.post()` 等
2. **请求验证**：从 `@validate_request()` 迁移到 Pydantic 模型
3. **用户认证**：从 `@login_required` 迁移到 `Depends(get_current_user)`
4. **参数获取**：从 `request.args` 迁移到 `Query()` 参数
5. **请求体**：从 `request.get_json()` 迁移到 Pydantic 模型

## 注意事项

- 所有路由函数现在是异步的 (`async def`)
- 使用 Pydantic 模型进行自动请求验证
- 错误处理使用 `HTTPException` 而不是返回错误响应
- 保持与现有 API 的向后兼容性

## 兼容性

- 保持与现有代码的向后兼容性
- 所有响应格式保持一致
- 错误代码和消息格式不变
- API 端点路径保持不变

## 文件结构

```
api/
├── apps/
│   └── kb_app.py          # 迁移后的 FastAPI 路由
├── models/
│   └── kb_models.py       # Pydantic 请求模型
└── utils/
    └── api_utils.py       # 工具函数（已迁移）
```
