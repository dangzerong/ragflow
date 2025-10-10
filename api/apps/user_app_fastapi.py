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
import json
import logging
import re
import secrets
from datetime import datetime
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr
try:
    from werkzeug.security import check_password_hash, generate_password_hash
except ImportError:
    # 如果没有werkzeug，使用passlib作为替代
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    def check_password_hash(hashed, password):
        return pwd_context.verify(password, hashed)
    
    def generate_password_hash(password):
        return pwd_context.hash(password)

from api import settings
from api.apps.auth import get_auth_client
from api.db import FileType, UserTenantRole
from api.db.db_models import TenantLLM
from api.db.services.file_service import FileService
from api.db.services.llm_service import get_init_tenant_llm
from api.db.services.tenant_llm_service import TenantLLMService
from api.db.services.user_service import TenantService, UserService, UserTenantService
from api.utils import (
    current_timestamp,
    datetime_format,
    download_img,
    get_format_time,
    get_uuid,
)
from api.utils.api_utils import (
    construct_response,
    get_data_error_result,
    get_json_result,
    server_error_response,
    validate_request,
)
from api.utils.crypt import decrypt

# 创建路由器
router = APIRouter()

# 安全方案
security = HTTPBearer()

# Pydantic模型
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RegisterRequest(BaseModel):
    nickname: str
    email: EmailStr
    password: str

class UserSettingRequest(BaseModel):
    nickname: Optional[str] = None
    password: Optional[str] = None
    new_password: Optional[str] = None

class TenantInfoRequest(BaseModel):
    tenant_id: str
    asr_id: str
    embd_id: str
    img2txt_id: str
    llm_id: str

# 依赖项：获取当前用户
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """获取当前用户"""
    from api.db import StatusEnum
    try:
        from itsdangerous.url_safe import URLSafeTimedSerializer as Serializer
    except ImportError:
        # 如果没有itsdangerous，使用jwt作为替代
        import jwt
        Serializer = jwt
    
    jwt = Serializer(secret_key=settings.SECRET_KEY)
    authorization = credentials.credentials
    
    if authorization:
        try:
            access_token = str(jwt.loads(authorization))
            
            if not access_token or not access_token.strip():
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication attempt with empty access token"
                )
            
            # Access tokens should be UUIDs (32 hex characters)
            if len(access_token.strip()) < 32:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Authentication attempt with invalid token format: {len(access_token)} chars"
                )
            
            user = UserService.query(
                access_token=access_token, status=StatusEnum.VALID.value
            )
            if user:
                if not user[0].access_token or not user[0].access_token.strip():
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail=f"User {user[0].email} has empty access_token in database"
                    )
                return user[0]
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid access token"
                )
        except Exception as e:
            logging.warning(f"load_user got exception {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid access token"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required"
        )

@router.post("/login")
async def login(request: LoginRequest):
    """
    用户登录端点
    """
    email = request.email
    users = UserService.query(email=email)
    if not users:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Email: {email} is not registered!"
        )

    password = request.password
    try:
        password = decrypt(password)
    except BaseException:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Fail to crypt password"
        )

    user = UserService.query_user(email, password)

    if user and hasattr(user, 'is_active') and user.is_active == "0":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been disabled, please contact the administrator!"
        )
    elif user:
        response_data = user.to_json()
        user.access_token = get_uuid()
        user.update_time = (current_timestamp(),)
        user.update_date = (datetime_format(datetime.now()),)
        user.save()
        msg = "Welcome back!"
        return construct_response(data=response_data, auth=user.get_id(), message=msg)
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email and password do not match!"
        )

@router.get("/login/channels")
async def get_login_channels():
    """
    获取所有支持的身份验证渠道
    """
    try:
        channels = []
        for channel, config in settings.OAUTH_CONFIG.items():
            channels.append(
                {
                    "channel": channel,
                    "display_name": config.get("display_name", channel.title()),
                    "icon": config.get("icon", "sso"),
                }
            )
        return get_json_result(data=channels)
    except Exception as e:
        logging.exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Load channels failure, error: {str(e)}"
        )

@router.get("/login/{channel}")
async def oauth_login(channel: str, request: Request):
    """OAuth登录"""
    channel_config = settings.OAUTH_CONFIG.get(channel)
    if not channel_config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid channel name: {channel}"
        )
    
    auth_cli = get_auth_client(channel_config)
    state = get_uuid()
    
    # 在FastAPI中，我们需要使用session来存储state
    # 这里简化处理，实际应该使用FastAPI的session管理
    auth_url = auth_cli.get_authorization_url(state)
    return RedirectResponse(url=auth_url)

@router.get("/oauth/callback/{channel}")
async def oauth_callback(channel: str, request: Request):
    """
    处理各种渠道的OAuth/OIDC回调
    """
    try:
        channel_config = settings.OAUTH_CONFIG.get(channel)
        if not channel_config:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid channel name: {channel}"
            )
        
        auth_cli = get_auth_client(channel_config)

        # 检查state
        state = request.query_params.get("state")
        # 在实际应用中，应该从session中获取state进行比较
        if not state:
            return RedirectResponse(url="/?error=invalid_state")

        # 获取授权码
        code = request.query_params.get("code")
        if not code:
            return RedirectResponse(url="/?error=missing_code")

        # 交换授权码获取访问令牌
        token_info = auth_cli.exchange_code_for_token(code)
        access_token = token_info.get("access_token")
        if not access_token:
            return RedirectResponse(url="/?error=token_failed")

        id_token = token_info.get("id_token")

        # 获取用户信息
        user_info = auth_cli.fetch_user_info(access_token, id_token=id_token)
        if not user_info.email:
            return RedirectResponse(url="/?error=email_missing")

        # 登录或注册
        users = UserService.query(email=user_info.email)
        user_id = get_uuid()

        if not users:
            try:
                try:
                    avatar = download_img(user_info.avatar_url)
                except Exception as e:
                    logging.exception(e)
                    avatar = ""

                users = user_register(
                    user_id,
                    {
                        "access_token": get_uuid(),
                        "email": user_info.email,
                        "avatar": avatar,
                        "nickname": user_info.nickname,
                        "login_channel": channel,
                        "last_login_time": get_format_time(),
                        "is_superuser": False,
                    },
                )

                if not users:
                    raise Exception(f"Failed to register {user_info.email}")
                if len(users) > 1:
                    raise Exception(f"Same email: {user_info.email} exists!")

                # 尝试登录
                user = users[0]
                return RedirectResponse(url=f"/?auth={user.get_id()}")

            except Exception as e:
                rollback_user_registration(user_id)
                logging.exception(e)
                return RedirectResponse(url=f"/?error={str(e)}")

        # 用户存在，尝试登录
        user = users[0]
        user.access_token = get_uuid()
        if user and hasattr(user, 'is_active') and user.is_active == "0":
            return RedirectResponse(url="/?error=user_inactive")

        user.save()
        return RedirectResponse(url=f"/?auth={user.get_id()}")
    except Exception as e:
        logging.exception(e)
        return RedirectResponse(url=f"/?error={str(e)}")

@router.get("/logout")
async def log_out(current_user = Depends(get_current_user)):
    """
    用户登出端点
    """
    current_user.access_token = f"INVALID_{secrets.token_hex(16)}"
    current_user.save()
    return get_json_result(data=True)

@router.post("/setting")
async def setting_user(request: UserSettingRequest, current_user = Depends(get_current_user)):
    """
    更新用户设置
    """
    update_dict = {}
    request_data = request.dict()
    
    if request_data.get("password"):
        new_password = request_data.get("new_password")
        if not check_password_hash(current_user.password, decrypt(request_data["password"])):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Password error!"
            )

        if new_password:
            update_dict["password"] = generate_password_hash(decrypt(new_password))

    for k in request_data.keys():
        if k in [
            "password",
            "new_password",
            "email",
            "status",
            "is_superuser",
            "login_channel",
            "is_anonymous",
            "is_active",
            "is_authenticated",
            "last_login_time",
        ]:
            continue
        update_dict[k] = request_data[k]

    try:
        UserService.update_by_id(current_user.id, update_dict)
        return get_json_result(data=True)
    except Exception as e:
        logging.exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Update failure!"
        )

@router.get("/info")
async def user_profile(current_user = Depends(get_current_user)):
    """
    获取用户配置文件信息
    """
    return get_json_result(data=current_user.to_dict())

def rollback_user_registration(user_id):
    """回滚用户注册"""
    try:
        UserService.delete_by_id(user_id)
    except Exception:
        pass
    try:
        TenantService.delete_by_id(user_id)
    except Exception:
        pass
    try:
        u = UserTenantService.query(tenant_id=user_id)
        if u:
            UserTenantService.delete_by_id(u[0].id)
    except Exception:
        pass
    try:
        TenantLLM.delete().where(TenantLLM.tenant_id == user_id).execute()
    except Exception:
        pass

def user_register(user_id, user):
    """用户注册"""
    user["id"] = user_id
    tenant = {
        "id": user_id,
        "name": user["nickname"] + "'s Kingdom",
        "llm_id": settings.CHAT_MDL,
        "embd_id": settings.EMBEDDING_MDL,
        "asr_id": settings.ASR_MDL,
        "parser_ids": settings.PARSERS,
        "img2txt_id": settings.IMAGE2TEXT_MDL,
        "rerank_id": settings.RERANK_MDL,
    }
    usr_tenant = {
        "tenant_id": user_id,
        "user_id": user_id,
        "invited_by": user_id,
        "role": UserTenantRole.OWNER,
    }
    file_id = get_uuid()
    file = {
        "id": file_id,
        "parent_id": file_id,
        "tenant_id": user_id,
        "created_by": user_id,
        "name": "/",
        "type": FileType.FOLDER.value,
        "size": 0,
        "location": "",
    }

    tenant_llm = get_init_tenant_llm(user_id)

    if not UserService.save(**user):
        return
    TenantService.insert(**tenant)
    UserTenantService.insert(**usr_tenant)
    TenantLLMService.insert_many(tenant_llm)
    FileService.insert(file)
    return UserService.query(email=user["email"])

@router.post("/register")
async def user_add(request: RegisterRequest):
    """
    注册新用户
    """
    if not settings.REGISTER_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User registration is disabled!"
        )

    email_address = request.email

    # 验证邮箱地址
    if not re.match(r"^[\w\._-]+@([\w_-]+\.)+[\w-]{2,}$", email_address):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid email address: {email_address}!"
        )

    # 检查邮箱地址是否已被使用
    if UserService.query(email=email_address):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Email: {email_address} has already registered!"
        )

    # 构建用户信息数据
    nickname = request.nickname
    user_dict = {
        "access_token": get_uuid(),
        "email": email_address,
        "nickname": nickname,
        "password": decrypt(request.password),
        "login_channel": "password",
        "last_login_time": get_format_time(),
        "is_superuser": False,
    }

    user_id = get_uuid()
    try:
        users = user_register(user_id, user_dict)
        if not users:
            raise Exception(f"Fail to register {email_address}.")
        if len(users) > 1:
            raise Exception(f"Same email: {email_address} exists!")
        user = users[0]
        return construct_response(
            data=user.to_json(),
            auth=user.get_id(),
            message=f"{nickname}, welcome aboard!",
        )
    except Exception as e:
        rollback_user_registration(user_id)
        logging.exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"User registration failure, error: {str(e)}"
        )

@router.get("/tenant_info")
async def tenant_info(current_user = Depends(get_current_user)):
    """
    获取租户信息
    """
    try:
        tenants = TenantService.get_info_by(current_user.id)
        if not tenants:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found!"
            )
        return get_json_result(data=tenants[0])
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/set_tenant_info")
async def set_tenant_info(request: TenantInfoRequest, current_user = Depends(get_current_user)):
    """
    更新租户信息
    """
    try:
        req_dict = request.dict()
        tid = req_dict.pop("tenant_id")
        TenantService.update_by_id(tid, req_dict)
        return get_json_result(data=True)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
