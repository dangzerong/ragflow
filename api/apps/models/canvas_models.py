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

from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field


class DeleteCanvasRequest(BaseModel):
    """删除画布请求"""
    canvas_ids: List[str] = Field(..., description="画布ID列表")


class SaveCanvasRequest(BaseModel):
    """保存画布请求"""
    dsl: Union[str, Dict[str, Any]] = Field(..., description="DSL配置")
    title: str = Field(..., description="画布标题")
    id: Optional[str] = Field(default=None, description="画布ID（更新时提供）")
    canvas_category: Optional[str] = Field(default=None, description="画布类别")
    description: Optional[str] = Field(default=None, description="描述")
    permission: Optional[str] = Field(default=None, description="权限")
    avatar: Optional[str] = Field(default=None, description="头像")


class CompletionRequest(BaseModel):
    """完成/运行画布请求"""
    id: str = Field(..., description="画布ID")
    query: Optional[str] = Field(default="", description="查询内容")
    files: Optional[List[str]] = Field(default=[], description="文件列表")
    inputs: Optional[Dict[str, Any]] = Field(default={}, description="输入参数")
    user_id: Optional[str] = Field(default=None, description="用户ID")


class RerunRequest(BaseModel):
    """重新运行请求"""
    id: str = Field(..., description="流水线ID")
    dsl: Dict[str, Any] = Field(..., description="DSL配置")
    component_id: str = Field(..., description="组件ID")


class ResetCanvasRequest(BaseModel):
    """重置画布请求"""
    id: str = Field(..., description="画布ID")


class InputFormQuery(BaseModel):
    """获取输入表单查询参数"""
    id: str = Field(..., description="画布ID")
    component_id: str = Field(..., description="组件ID")


class DebugRequest(BaseModel):
    """调试请求"""
    id: str = Field(..., description="画布ID")
    component_id: str = Field(..., description="组件ID")
    params: Dict[str, Any] = Field(..., description="参数")


class TestDBConnectRequest(BaseModel):
    """测试数据库连接请求"""
    db_type: str = Field(..., description="数据库类型")
    database: str = Field(..., description="数据库名")
    username: str = Field(..., description="用户名")
    host: str = Field(..., description="主机")
    port: str = Field(..., description="端口")
    password: str = Field(..., description="密码")


class ListCanvasQuery(BaseModel):
    """列出画布查询参数"""
    keywords: Optional[str] = Field(default="", description="关键词")
    page: Optional[int] = Field(default=0, description="页码")
    page_size: Optional[int] = Field(default=0, description="每页大小")
    orderby: Optional[str] = Field(default="create_time", description="排序字段")
    desc: Optional[str] = Field(default="true", description="是否降序")
    canvas_category: Optional[str] = Field(default=None, description="画布类别")
    owner_ids: Optional[str] = Field(default="", description="所有者ID列表（逗号分隔）")


class SettingRequest(BaseModel):
    """画布设置请求"""
    id: str = Field(..., description="画布ID")
    title: str = Field(..., description="标题")
    permission: str = Field(..., description="权限")
    description: Optional[str] = Field(default=None, description="描述")
    avatar: Optional[str] = Field(default=None, description="头像")


class TraceQuery(BaseModel):
    """追踪查询参数"""
    canvas_id: str = Field(..., description="画布ID")
    message_id: str = Field(..., description="消息ID")


class ListSessionsQuery(BaseModel):
    """列出会话查询参数"""
    user_id: Optional[str] = Field(default=None, description="用户ID")
    page: Optional[int] = Field(default=1, description="页码")
    page_size: Optional[int] = Field(default=30, description="每页大小")
    keywords: Optional[str] = Field(default=None, description="关键词")
    from_date: Optional[str] = Field(default=None, description="开始日期")
    to_date: Optional[str] = Field(default=None, description="结束日期")
    orderby: Optional[str] = Field(default="update_time", description="排序字段")
    desc: Optional[str] = Field(default="true", description="是否降序")
    dsl: Optional[str] = Field(default="true", description="是否包含DSL")


class DownloadQuery(BaseModel):
    """下载查询参数"""
    id: str = Field(..., description="文件ID")
    created_by: str = Field(..., description="创建者ID")


class UploadQuery(BaseModel):
    """上传查询参数"""
    url: Optional[str] = Field(default=None, description="URL（可选，用于从URL下载）")

