#
#  Copyright 2024 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

from typing import Optional
from fastapi import Depends, Header, Security, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from api import settings
from api.utils.api_utils import get_json_result

# 创建 HTTPBearer 安全方案（auto_error=False 允许我们自定义错误处理）
http_bearer = HTTPBearer(auto_error=False)


def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Security(http_bearer)):
    """FastAPI 依赖注入：获取当前用户（替代 Flask 的 login_required 和 current_user）
    
    使用 Security(http_bearer) 可以让 FastAPI 自动在 OpenAPI schema 中添加安全要求，
    这样 Swagger UI 就会显示授权输入框并自动在请求中添加 Authorization 头。
    """
    # 延迟导入以避免循环导入
    from api.apps.__init___fastapi import get_current_user_from_token
    
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is required"
        )
    
    # HTTPBearer 已经提取了 Bearer token，credentials.credentials 就是 token 本身
    authorization = credentials.credentials
    
    user = get_current_user_from_token(authorization)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    return user

