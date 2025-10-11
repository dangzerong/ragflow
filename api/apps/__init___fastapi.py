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
import os
import sys
import logging
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.sessions import SessionMiddleware
try:
    from itsdangerous.url_safe import URLSafeTimedSerializer as Serializer
except ImportError:
    # 如果没有itsdangerous，使用jwt作为替代
    import jwt
    Serializer = jwt

from api.db import StatusEnum
from api.db.db_models import close_connection
from api.db.services import UserService
from api.utils.json import CustomJSONEncoder
from api.utils import commands

from api import settings
from api.utils.api_utils import server_error_response
from api.constants import API_VERSION

__all__ = ["app"]

def create_app() -> FastAPI:
    """创建FastAPI应用实例"""
    app = FastAPI(
        title="RAGFlow API",
        description="RAGFlow API Server",
        version="1.0.0",
        docs_url="/apidocs/",
        redoc_url="/redoc/",
        openapi_url="/apispec.json"
    )
    
    # 添加CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 生产环境中应该设置具体的域名
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        max_age=2592000
    )
    
    # 添加信任主机中间件
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"]  # 生产环境中应该设置具体的域名
    )
    
    # 添加会话中间件
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.SECRET_KEY,
        max_age=2592000
    )
    
    # 设置错误处理器
    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        return server_error_response(exc)
    
    return app

def search_pages_path(pages_dir):
    """搜索页面路径"""
    app_path_list = [
        path for path in pages_dir.glob("*_app_fastapi.py") if not path.name.startswith(".")
    ]
    api_path_list = [
        path for path in pages_dir.glob("*sdk/*.py") if not path.name.startswith(".")
    ]
    app_path_list.extend(api_path_list)
    return app_path_list

def register_page(app: FastAPI, page_path):
    """注册页面路由"""
    path = f"{page_path}"

    page_name = page_path.stem.removesuffix("_app_fastapi")
    module_name = ".".join(
        page_path.parts[page_path.parts.index("api"): -1] + (page_name,)
    )

    spec = spec_from_file_location(module_name, page_path)
    page = module_from_spec(spec)
    page.app = app
    page.router = None  # FastAPI使用router而不是Blueprint
    sys.modules[module_name] = page
    spec.loader.exec_module(page)
    page_name = getattr(page, "page_name", page_name)
    sdk_path = "\\sdk\\" if sys.platform.startswith("win") else "/sdk/"
    url_prefix = (
        f"/api/{API_VERSION}" if sdk_path in path else f"/{API_VERSION}/{page_name}"
    )

    # 在FastAPI中，我们需要检查是否有router属性
    if hasattr(page, 'router') and page.router:
        app.include_router(page.router, prefix=url_prefix)
    return url_prefix

def setup_routes(app: FastAPI):
    """设置路由 - 注册所有接口"""
    from api.apps.user_app_fastapi import router as user_router
    from api.apps.kb_app import router as kb_router
    from api.apps.document_app import router as document_router

    app.include_router(user_router, prefix=f"/{API_VERSION}/user", tags=["User"])
    app.include_router(kb_router, prefix=f"/{API_VERSION}/kb", tags=["KB"])
    app.include_router(document_router, prefix=f"/{API_VERSION}/document", tags=["Document"])

def get_current_user_from_token(authorization: str):
    """从token获取当前用户"""
    jwt = Serializer(secret_key=settings.SECRET_KEY)
    
    if authorization:
        try:
            access_token = str(jwt.loads(authorization))
            
            if not access_token or not access_token.strip():
                logging.warning("Authentication attempt with empty access token")
                return None
            
            # Access tokens should be UUIDs (32 hex characters)
            if len(access_token.strip()) < 32:
                logging.warning(f"Authentication attempt with invalid token format: {len(access_token)} chars")
                return None
            
            user = UserService.query(
                access_token=access_token, status=StatusEnum.VALID.value
            )
            if user:
                if not user[0].access_token or not user[0].access_token.strip():
                    logging.warning(f"User {user[0].email} has empty access_token in database")
                    return None
                return user[0]
            else:
                return None
        except Exception as e:
            logging.warning(f"load_user got exception {e}")
            return None
    else:
        return None

# 创建应用实例
app = create_app()

@app.middleware("http")
async def db_close_middleware(request, call_next):
    """数据库连接关闭中间件"""
    try:
        response = await call_next(request)
        return response
    finally:
        close_connection()

setup_routes(app)
