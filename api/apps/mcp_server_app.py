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
from fastapi import APIRouter, Depends, Query

from api.apps.models.auth_dependencies import get_current_user
from api.apps.models.mcp_models import (
    ListMCPServersQuery,
    ListMCPServersBody,
    CreateMCPServerRequest,
    UpdateMCPServerRequest,
    DeleteMCPServersRequest,
    ImportMCPServersRequest,
    ExportMCPServersRequest,
    ListMCPToolsRequest,
    TestMCPToolRequest,
    CacheMCPToolsRequest,
    TestMCPRequest,
)

from api.db import VALID_MCP_SERVER_TYPES
from api.db.db_models import MCPServer
from api.db.services.mcp_server_service import MCPServerService
from api.db.services.user_service import TenantService
from api.settings import RetCode

from api.utils import get_uuid
from api.utils.api_utils import get_data_error_result, get_json_result, server_error_response, get_mcp_tools
from api.utils.web_utils import safe_json_parse
from rag.utils.mcp_tool_call_conn import MCPToolCallSession, close_multiple_mcp_toolcall_sessions

# 创建路由器
router = APIRouter()


@router.post("/list")
async def list_mcp(
    query: ListMCPServersQuery = Depends(),
    body: ListMCPServersBody = None,
    current_user = Depends(get_current_user)
):
    """列出MCP服务器"""
    if body is None:
        body = ListMCPServersBody()
    
    keywords = query.keywords or ""
    page_number = int(query.page or 0)
    items_per_page = int(query.page_size or 0)
    orderby = query.orderby or "create_time"
    desc = query.desc.lower() == "true" if query.desc else True

    mcp_ids = body.mcp_ids or []
    try:
        servers = MCPServerService.get_servers(current_user.id, mcp_ids, 0, 0, orderby, desc, keywords) or []
        total = len(servers)

        if page_number and items_per_page:
            servers = servers[(page_number - 1) * items_per_page : page_number * items_per_page]

        return get_json_result(data={"mcp_servers": servers, "total": total})
    except Exception as e:
        return server_error_response(e)


@router.get("/detail")
async def detail(
    mcp_id: str = Query(..., description="MCP服务器ID"),
    current_user = Depends(get_current_user)
):
    """获取MCP服务器详情"""
    try:
        mcp_server = MCPServerService.get_or_none(id=mcp_id, tenant_id=current_user.id)

        if mcp_server is None:
            return get_json_result(code=RetCode.NOT_FOUND, data=None)

        return get_json_result(data=mcp_server.to_dict())
    except Exception as e:
        return server_error_response(e)


@router.post("/create")
async def create(
    request: CreateMCPServerRequest,
    current_user = Depends(get_current_user)
):
    """创建MCP服务器"""
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

    timeout = request.timeout or 10.0

    try:
        req = {
            "id": get_uuid(),
            "tenant_id": current_user.id,
            "name": server_name,
            "url": url,
            "server_type": server_type,
            "headers": headers,
            "variables": variables,
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
        req["variables"] = variables

        if not MCPServerService.insert(**req):
            return get_data_error_result("Failed to create MCP server.")

        return get_json_result(data=req)
    except Exception as e:
        return server_error_response(e)


@router.post("/update")
async def update(
    request: UpdateMCPServerRequest,
    current_user = Depends(get_current_user)
):
    """更新MCP服务器"""
    mcp_id = request.mcp_id
    e, mcp_server = MCPServerService.get_by_id(mcp_id)
    if not e or mcp_server.tenant_id != current_user.id:
        return get_data_error_result(message=f"Cannot find MCP server {mcp_id} for user {current_user.id}")

    server_type = request.server_type if request.server_type is not None else mcp_server.server_type
    if server_type and server_type not in VALID_MCP_SERVER_TYPES:
        return get_data_error_result(message="Unsupported MCP server type.")
    server_name = request.name if request.name is not None else mcp_server.name
    if server_name and len(server_name.encode("utf-8")) > 255:
        return get_data_error_result(message=f"Invalid MCP name or length is {len(server_name)} which is large than 255.")
    url = request.url if request.url is not None else mcp_server.url
    if not url:
        return get_data_error_result(message="Invalid url.")

    headers = safe_json_parse(request.headers if request.headers is not None else mcp_server.headers)
    variables = safe_json_parse(request.variables if request.variables is not None else mcp_server.variables)
    variables.pop("tools", None)

    timeout = request.timeout or 10.0

    try:
        req = {
            "tenant_id": current_user.id,
            "id": mcp_id,
            "name": server_name,
            "url": url,
            "server_type": server_type,
            "headers": headers,
            "variables": variables,
        }

        mcp_server = MCPServer(id=server_name, name=server_name, url=url, server_type=server_type, variables=variables, headers=headers)
        server_tools, err_message = get_mcp_tools([mcp_server], timeout)
        if err_message:
            return get_data_error_result(err_message)

        tools = server_tools[server_name]
        tools = {tool["name"]: tool for tool in tools if isinstance(tool, dict) and "name" in tool}
        variables["tools"] = tools
        req["variables"] = variables

        if not MCPServerService.filter_update([MCPServer.id == mcp_id, MCPServer.tenant_id == current_user.id], req):
            return get_data_error_result(message="Failed to updated MCP server.")

        e, updated_mcp = MCPServerService.get_by_id(req["id"])
        if not e:
            return get_data_error_result(message="Failed to fetch updated MCP server.")

        return get_json_result(data=updated_mcp.to_dict())
    except Exception as e:
        return server_error_response(e)


@router.post("/rm")
async def rm(
    request: DeleteMCPServersRequest,
    current_user = Depends(get_current_user)
):
    """删除MCP服务器"""
    mcp_ids = request.mcp_ids

    try:
        if not MCPServerService.delete_by_ids(mcp_ids):
            return get_data_error_result(message=f"Failed to delete MCP servers {mcp_ids}")

        return get_json_result(data=True)
    except Exception as e:
        return server_error_response(e)


@router.post("/import")
async def import_multiple(
    request: ImportMCPServersRequest,
    current_user = Depends(get_current_user)
):
    """批量导入MCP服务器"""
    servers = request.mcpServers
    if not servers:
        return get_data_error_result(message="No MCP servers provided.")

    timeout = request.timeout or 10.0

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
    request: ExportMCPServersRequest,
    current_user = Depends(get_current_user)
):
    """批量导出MCP服务器"""
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
async def list_tools(
    request: ListMCPToolsRequest,
    current_user = Depends(get_current_user)
):
    """列出MCP工具"""
    mcp_ids = request.mcp_ids
    if not mcp_ids:
        return get_data_error_result(message="No MCP server IDs provided.")

    timeout = request.timeout or 10.0

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
async def test_tool(
    request: TestMCPToolRequest,
    current_user = Depends(get_current_user)
):
    """测试MCP工具"""
    mcp_id = request.mcp_id
    if not mcp_id:
        return get_data_error_result(message="No MCP server ID provided.")

    timeout = request.timeout or 10.0

    tool_name = request.tool_name
    arguments = request.arguments
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
async def cache_tool(
    request: CacheMCPToolsRequest,
    current_user = Depends(get_current_user)
):
    """缓存MCP工具"""
    mcp_id = request.mcp_id
    if not mcp_id:
        return get_data_error_result(message="No MCP server ID provided.")
    tools = request.tools

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
async def test_mcp(
    request: TestMCPRequest
):
    """测试MCP服务器（不需要登录）"""
    url = request.url
    if not url:
        return get_data_error_result(message="Invalid MCP url.")

    server_type = request.server_type
    if server_type not in VALID_MCP_SERVER_TYPES:
        return get_data_error_result(message="Unsupported MCP server type.")

    timeout = request.timeout or 10.0
    headers = safe_json_parse(request.headers or {})
    variables = safe_json_parse(request.variables or {})

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
