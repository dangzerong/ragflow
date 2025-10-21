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
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from api import settings
from api.db import VALID_MCP_SERVER_TYPES
from api.db.db_models import MCPServer, User
from api.db.services.mcp_server_service import MCPServerService
from api.db.services.user_service import TenantService
from api.settings import RetCode

from api.utils import get_uuid
from api.utils.api_utils import get_data_error_result, get_json_result, server_error_response, get_mcp_tools
from api.utils.web_utils import get_float, safe_json_parse
from rag.utils.mcp_tool_call_conn import MCPToolCallSession, close_multiple_mcp_toolcall_sessions
from pydantic import BaseModel

# Security
security = HTTPBearer()

# Pydantic models for request/response
class ListMCPRequest(BaseModel):
    mcp_ids: List[str] = []

class CreateMCPRequest(BaseModel):
    name: str
    url: str
    server_type: str
    headers: Optional[Dict[str, Any]] = {}
    variables: Optional[Dict[str, Any]] = {}
    timeout: Optional[float] = 10

class UpdateMCPRequest(BaseModel):
    mcp_id: str
    name: Optional[str] = None
    url: Optional[str] = None
    server_type: Optional[str] = None
    headers: Optional[Dict[str, Any]] = None
    variables: Optional[Dict[str, Any]] = None
    timeout: Optional[float] = 10

class RemoveMCPRequest(BaseModel):
    mcp_ids: List[str]

class ImportMCPRequest(BaseModel):
    mcpServers: Dict[str, Dict[str, Any]]
    timeout: Optional[float] = 10

class ExportMCPRequest(BaseModel):
    mcp_ids: List[str]


class ListToolsRequest(BaseModel):
    mcp_ids: List[str]
    timeout: Optional[float] = 10


class TestToolRequest(BaseModel):
    mcp_id: str
    tool_name: str
    arguments: Dict[str, Any]
    timeout: Optional[float] = 10


class CacheToolsRequest(BaseModel):
    mcp_id: str
    tools: List[Dict[str, Any]]


class TestMCPRequest(BaseModel):
    url: str
    server_type: str
    timeout: Optional[float] = 10
    headers: Optional[Dict[str, Any]] = {}
    variables: Optional[Dict[str, Any]] = {}

# Dependency injection
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """获取当前用户"""
    from api.db import StatusEnum
    from api.db.services.user_service import UserService
    from fastapi import HTTPException, status
    import logging
    
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

# Create router
router = APIRouter()


@router.post("/list")
async def list_mcp(
    request: ListMCPRequest,
    keywords: str = Query("", description="Search keywords"),
    page: int = Query(0, description="Page number"),
    page_size: int = Query(0, description="Items per page"),
    orderby: str = Query("create_time", description="Order by field"),
    desc: bool = Query(True, description="Sort descending"),
    current_user: User = Depends(get_current_user)
):
    try:
        servers = MCPServerService.get_servers(current_user.id, request.mcp_ids, 0, 0, orderby, desc, keywords) or []
        total = len(servers)

        if page and page_size:
            servers = servers[(page - 1) * page_size : page * page_size]

        return get_json_result(data={"mcp_servers": servers, "total": total})
    except Exception as e:
        return server_error_response(e)


@router.get("/detail")
async def detail(
    mcp_id: str = Query(..., description="MCP server ID"),
    current_user: User = Depends(get_current_user)
):
    try:
        mcp_server = MCPServerService.get_or_none(id=mcp_id, tenant_id=current_user.id)

        if mcp_server is None:
            return get_json_result(code=RetCode.NOT_FOUND, data=None)

        return get_json_result(data=mcp_server.to_dict())
    except Exception as e:
        return server_error_response(e)


@router.post("/create")
async def create(
    request: CreateMCPRequest,
    current_user: User = Depends(get_current_user)
):
    server_type = request.server_type
    if server_type not in VALID_MCP_SERVER_TYPES:
        return get_data_error_result(message="Unsupported MCP server type.")

    server_name = request.name
    if not server_name or len(server_name.encode("utf-8")) > 255:
        return get_data_error_result(message=f"Invalid MCP name or length is {len(server_name)} which is large than 255.")

    e, _ = MCPServerService.get_by_name_and_tenant(name=server_name, tenant_id=current_user.id)
    if e:
        return get_data_error_result(message="Duplicated MCP server name.")

    url = request.url
    if not url:
        return get_data_error_result(message="Invalid url.")

    headers = safe_json_parse(request.headers or {})
    variables = safe_json_parse(request.variables or {})
    variables.pop("tools", None)

    timeout = request.timeout or 10

    try:
        req_data = {
            "id": get_uuid(),
            "tenant_id": current_user.id,
            "name": server_name,
            "url": url,
            "server_type": server_type,
            "headers": headers,
            "variables": variables,
            "timeout": timeout
        }

        e, _ = TenantService.get_by_id(current_user.id)
        if not e:
            return get_data_error_result(message="Tenant not found.")

        mcp_server = MCPServer(id=server_name, name=server_name, url=url, server_type=server_type, variables=variables, headers=headers)
        server_tools, err_message = get_mcp_tools([mcp_server], timeout)
        if err_message:
            return get_data_error_result(err_message)

        tools = server_tools[server_name]
        tools = {tool["name"]: tool for tool in tools if isinstance(tool, dict) and "name" in tool}
        variables["tools"] = tools
        req_data["variables"] = variables

        if not MCPServerService.insert(**req_data):
            return get_data_error_result("Failed to create MCP server.")

        return get_json_result(data=req_data)
    except Exception as e:
        return server_error_response(e)


@router.post("/update")
async def update(
    request: UpdateMCPRequest,
    current_user: User = Depends(get_current_user)
):
    mcp_id = request.mcp_id
    e, mcp_server = MCPServerService.get_by_id(mcp_id)
    if not e or mcp_server.tenant_id != current_user.id:
        return get_data_error_result(message=f"Cannot find MCP server {mcp_id} for user {current_user.id}")

    server_type = request.server_type or mcp_server.server_type
    if server_type and server_type not in VALID_MCP_SERVER_TYPES:
        return get_data_error_result(message="Unsupported MCP server type.")
    
    server_name = request.name or mcp_server.name
    if server_name and len(server_name.encode("utf-8")) > 255:
        return get_data_error_result(message=f"Invalid MCP name or length is {len(server_name)} which is large than 255.")
    
    url = request.url or mcp_server.url
    if not url:
        return get_data_error_result(message="Invalid url.")

    headers = safe_json_parse(request.headers or mcp_server.headers)
    variables = safe_json_parse(request.variables or mcp_server.variables)
    variables.pop("tools", None)

    timeout = request.timeout or 10

    try:
        req_data = {
            "tenant_id": current_user.id,
            "id": mcp_id,
            "name": server_name,
            "url": url,
            "server_type": server_type,
            "headers": headers,
            "variables": variables,
            "timeout": timeout
        }

        mcp_server = MCPServer(id=server_name, name=server_name, url=url, server_type=server_type, variables=variables, headers=headers)
        server_tools, err_message = get_mcp_tools([mcp_server], timeout)
        if err_message:
            return get_data_error_result(err_message)

        tools = server_tools[server_name]
        tools = {tool["name"]: tool for tool in tools if isinstance(tool, dict) and "name" in tool}
        variables["tools"] = tools
        req_data["variables"] = variables

        if not MCPServerService.filter_update([MCPServer.id == mcp_id, MCPServer.tenant_id == current_user.id], req_data):
            return get_data_error_result(message="Failed to updated MCP server.")

        e, updated_mcp = MCPServerService.get_by_id(req_data["id"])
        if not e:
            return get_data_error_result(message="Failed to fetch updated MCP server.")

        return get_json_result(data=updated_mcp.to_dict())
    except Exception as e:
        return server_error_response(e)


@router.post("/rm")
async def rm(
    request: RemoveMCPRequest,
    current_user: User = Depends(get_current_user)
):
    mcp_ids = request.mcp_ids

    try:
        if not MCPServerService.delete_by_ids(mcp_ids):
            return get_data_error_result(message=f"Failed to delete MCP servers {mcp_ids}")

        return get_json_result(data=True)
    except Exception as e:
        return server_error_response(e)


@router.post("/import")
async def import_multiple(
    request: ImportMCPRequest,
    current_user: User = Depends(get_current_user)
):
    servers = request.mcpServers
    if not servers:
        return get_data_error_result(message="No MCP servers provided.")

    timeout = request.timeout or 10

    results = []
    try:
        for server_name, config in servers.items():
            if not all(key in config for key in {"type", "url"}):
                results.append({"server": server_name, "success": False, "message": "Missing required fields (type or url)"})
                continue

            if not server_name or len(server_name.encode("utf-8")) > 255:
                results.append({"server": server_name, "success": False, "message": f"Invalid MCP name or length is {len(server_name)} which is large than 255."})
                continue

            base_name = server_name
            new_name = base_name
            counter = 0

            while True:
                e, _ = MCPServerService.get_by_name_and_tenant(name=new_name, tenant_id=current_user.id)
                if not e:
                    break
                new_name = f"{base_name}_{counter}"
                counter += 1

            create_data = {
                "id": get_uuid(),
                "tenant_id": current_user.id,
                "name": new_name,
                "url": config["url"],
                "server_type": config["type"],
                "variables": {"authorization_token": config.get("authorization_token", "")},
            }

            headers = {"authorization_token": config["authorization_token"]} if "authorization_token" in config else {}
            variables = {k: v for k, v in config.items() if k not in {"type", "url", "headers"}}
            mcp_server = MCPServer(id=new_name, name=new_name, url=config["url"], server_type=config["type"], variables=variables, headers=headers)
            server_tools, err_message = get_mcp_tools([mcp_server], timeout)
            if err_message:
                results.append({"server": base_name, "success": False, "message": err_message})
                continue

            tools = server_tools[new_name]
            tools = {tool["name"]: tool for tool in tools if isinstance(tool, dict) and "name" in tool}
            create_data["variables"]["tools"] = tools

            if MCPServerService.insert(**create_data):
                result = {"server": server_name, "success": True, "action": "created", "id": create_data["id"], "new_name": new_name}
                if new_name != base_name:
                    result["message"] = f"Renamed from '{base_name}' to '{new_name}' avoid duplication"
                results.append(result)
            else:
                results.append({"server": server_name, "success": False, "message": "Failed to create MCP server."})

        return get_json_result(data={"results": results})
    except Exception as e:
        return server_error_response(e)


@router.post("/export")
async def export_multiple(
    request: ExportMCPRequest,
    current_user: User = Depends(get_current_user)
):
    mcp_ids = request.mcp_ids

    if not mcp_ids:
        return get_data_error_result(message="No MCP server IDs provided.")

    try:
        exported_servers = {}

        for mcp_id in mcp_ids:
            e, mcp_server = MCPServerService.get_by_id(mcp_id)

            if e and mcp_server.tenant_id == current_user.id:
                server_key = mcp_server.name

                exported_servers[server_key] = {
                    "type": mcp_server.server_type,
                    "url": mcp_server.url,
                    "name": mcp_server.name,
                    "authorization_token": mcp_server.variables.get("authorization_token", ""),
                    "tools": mcp_server.variables.get("tools", {}),
                }

        return get_json_result(data={"mcpServers": exported_servers})
    except Exception as e:
        return server_error_response(e)


@router.post("/list_tools")
async def list_tools(req: ListToolsRequest, current_user: User = Depends(get_current_user)):
    mcp_ids = req.mcp_ids
    if not mcp_ids:
        return get_data_error_result(message="No MCP server IDs provided.")

    timeout = req.timeout

    results = {}
    tool_call_sessions = []
    try:
        for mcp_id in mcp_ids:
            e, mcp_server = MCPServerService.get_by_id(mcp_id)

            if e and mcp_server.tenant_id == current_user.id:
                server_key = mcp_server.id

                cached_tools = mcp_server.variables.get("tools", {})

                tool_call_session = MCPToolCallSession(mcp_server, mcp_server.variables)
                tool_call_sessions.append(tool_call_session)

                try:
                    tools = tool_call_session.get_tools(timeout)
                except Exception as e:
                    tools = []
                    return get_data_error_result(message=f"MCP list tools error: {e}")

                results[server_key] = []
                for tool in tools:
                    tool_dict = tool.model_dump()
                    cached_tool = cached_tools.get(tool_dict["name"], {})

                    tool_dict["enabled"] = cached_tool.get("enabled", True)
                    results[server_key].append(tool_dict)

        return get_json_result(data=results)
    except Exception as e:
        return server_error_response(e)
    finally:
        # PERF: blocking call to close sessions — consider moving to background thread or task queue
        close_multiple_mcp_toolcall_sessions(tool_call_sessions)


@router.post("/test_tool")
async def test_tool(req: TestToolRequest, current_user: User = Depends(get_current_user)):
    mcp_id = req.mcp_id
    if not mcp_id:
        return get_data_error_result(message="No MCP server ID provided.")

    timeout = req.timeout

    tool_name = req.tool_name
    arguments = req.arguments
    if not all([tool_name, arguments]):
        return get_data_error_result(message="Require provide tool name and arguments.")

    tool_call_sessions = []
    try:
        e, mcp_server = MCPServerService.get_by_id(mcp_id)
        if not e or mcp_server.tenant_id != current_user.id:
            return get_data_error_result(message=f"Cannot find MCP server {mcp_id} for user {current_user.id}")

        tool_call_session = MCPToolCallSession(mcp_server, mcp_server.variables)
        tool_call_sessions.append(tool_call_session)
        result = tool_call_session.tool_call(tool_name, arguments, timeout)

        # PERF: blocking call to close sessions — consider moving to background thread or task queue
        close_multiple_mcp_toolcall_sessions(tool_call_sessions)
        return get_json_result(data=result)
    except Exception as e:
        return server_error_response(e)


@router.post("/cache_tools")
async def cache_tool(req: CacheToolsRequest, current_user: User = Depends(get_current_user)):
    mcp_id = req.mcp_id
    if not mcp_id:
        return get_data_error_result(message="No MCP server ID provided.")
    tools = req.tools

    e, mcp_server = MCPServerService.get_by_id(mcp_id)
    if not e or mcp_server.tenant_id != current_user.id:
        return get_data_error_result(message=f"Cannot find MCP server {mcp_id} for user {current_user.id}")

    variables = mcp_server.variables
    tools = {tool["name"]: tool for tool in tools if isinstance(tool, dict) and "name" in tool}
    variables["tools"] = tools

    if not MCPServerService.filter_update([MCPServer.id == mcp_id, MCPServer.tenant_id == current_user.id], {"variables": variables}):
        return get_data_error_result(message="Failed to updated MCP server.")

    return get_json_result(data=tools)


@router.post("/test_mcp")
async def test_mcp(req: TestMCPRequest):
    url = req.url
    if not url:
        return get_data_error_result(message="Invalid MCP url.")

    server_type = req.server_type
    if server_type not in VALID_MCP_SERVER_TYPES:
        return get_data_error_result(message="Unsupported MCP server type.")

    timeout = req.timeout
    headers = req.headers
    variables = req.variables

    mcp_server = MCPServer(id=f"{server_type}: {url}", server_type=server_type, url=url, headers=headers, variables=variables)

    result = []
    try:
        tool_call_session = MCPToolCallSession(mcp_server, mcp_server.variables)

        try:
            tools = tool_call_session.get_tools(timeout)
        except Exception as e:
            tools = []
            return get_data_error_result(message=f"Test MCP error: {e}")
        finally:
            # PERF: blocking call to close sessions — consider moving to background thread or task queue
            close_multiple_mcp_toolcall_sessions([tool_call_session])

        for tool in tools:
            tool_dict = tool.model_dump()
            tool_dict["enabled"] = True
            result.append(tool_dict)

        return get_json_result(data=result)
    except Exception as e:
        return server_error_response(e)
