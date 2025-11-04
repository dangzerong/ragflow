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

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ListMCPServersQuery(BaseModel):
    """列出MCP服务器查询参数"""
    keywords: Optional[str] = Field(default="", description="关键词")
    page: Optional[int] = Field(default=0, description="页码")
    page_size: Optional[int] = Field(default=0, description="每页大小")
    orderby: Optional[str] = Field(default="create_time", description="排序字段")
    desc: Optional[str] = Field(default="true", description="是否降序")


class ListMCPServersBody(BaseModel):
    """列出MCP服务器请求体"""
    mcp_ids: Optional[List[str]] = Field(default=[], description="MCP服务器ID列表")


class CreateMCPServerRequest(BaseModel):
    """创建MCP服务器请求"""
    name: str = Field(..., description="服务器名称")
    url: str = Field(..., description="服务器URL")
    server_type: str = Field(..., description="服务器类型")
    headers: Optional[Dict[str, Any]] = Field(default={}, description="请求头")
    variables: Optional[Dict[str, Any]] = Field(default={}, description="变量")
    timeout: Optional[float] = Field(default=10.0, description="超时时间")


class UpdateMCPServerRequest(BaseModel):
    """更新MCP服务器请求"""
    mcp_id: str = Field(..., description="MCP服务器ID")
    name: Optional[str] = Field(default=None, description="服务器名称")
    url: Optional[str] = Field(default=None, description="服务器URL")
    server_type: Optional[str] = Field(default=None, description="服务器类型")
    headers: Optional[Dict[str, Any]] = Field(default=None, description="请求头")
    variables: Optional[Dict[str, Any]] = Field(default=None, description="变量")
    timeout: Optional[float] = Field(default=10.0, description="超时时间")


class DeleteMCPServersRequest(BaseModel):
    """删除MCP服务器请求"""
    mcp_ids: List[str] = Field(..., description="MCP服务器ID列表")


class ImportMCPServersRequest(BaseModel):
    """批量导入MCP服务器请求"""
    mcpServers: Dict[str, Any] = Field(..., description="MCP服务器配置字典")
    timeout: Optional[float] = Field(default=10.0, description="超时时间")


class ExportMCPServersRequest(BaseModel):
    """批量导出MCP服务器请求"""
    mcp_ids: List[str] = Field(..., description="MCP服务器ID列表")


class ListMCPToolsRequest(BaseModel):
    """列出MCP工具请求"""
    mcp_ids: List[str] = Field(..., description="MCP服务器ID列表")
    timeout: Optional[float] = Field(default=10.0, description="超时时间")


class TestMCPToolRequest(BaseModel):
    """测试MCP工具请求"""
    mcp_id: str = Field(..., description="MCP服务器ID")
    tool_name: str = Field(..., description="工具名称")
    arguments: Dict[str, Any] = Field(..., description="工具参数")
    timeout: Optional[float] = Field(default=10.0, description="超时时间")


class CacheMCPToolsRequest(BaseModel):
    """缓存MCP工具请求"""
    mcp_id: str = Field(..., description="MCP服务器ID")
    tools: List[Dict[str, Any]] = Field(..., description="工具列表")


class TestMCPRequest(BaseModel):
    """测试MCP服务器请求（不需要登录）"""
    url: str = Field(..., description="服务器URL")
    server_type: str = Field(..., description="服务器类型")
    headers: Optional[Dict[str, Any]] = Field(default={}, description="请求头")
    variables: Optional[Dict[str, Any]] = Field(default={}, description="变量")
    timeout: Optional[float] = Field(default=10.0, description="超时时间")

