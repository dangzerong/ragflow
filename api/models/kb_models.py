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


class CreateKnowledgeBaseRequest(BaseModel):
    """创建知识库请求模型"""
    name: str = Field(..., description="知识库名称")
    description: Optional[str] = Field(None, description="知识库描述")
    parser_id: Optional[str] = Field("naive", description="解析器ID")
    parser_config: Optional[Dict[str, Any]] = Field(None, description="解析器配置")
    embd_id: Optional[str] = Field(None, description="嵌入模型ID")


class UpdateKnowledgeBaseRequest(BaseModel):
    """更新知识库请求模型"""
    kb_id: str = Field(..., description="知识库ID")
    name: str = Field(..., description="知识库名称")
    pagerank: Optional[int] = Field(0, description="页面排名")


class DeleteKnowledgeBaseRequest(BaseModel):
    """删除知识库请求模型"""
    kb_id: str = Field(..., description="知识库ID")


class ListKnowledgeBasesRequest(BaseModel):
    """列出知识库请求模型"""
    owner_ids: Optional[List[str]] = Field([], description="所有者ID列表")


class RemoveTagsRequest(BaseModel):
    """移除标签请求模型"""
    tags: List[str] = Field(..., description="要移除的标签列表")


class RenameTagRequest(BaseModel):
    """重命名标签请求模型"""
    from_tag: str = Field(..., description="原标签名")
    to_tag: str = Field(..., description="新标签名")


class RunGraphRAGRequest(BaseModel):
    """运行GraphRAG请求模型"""
    kb_id: str = Field(..., description="知识库ID")


class RunRaptorRequest(BaseModel):
    """运行RAPTOR请求模型"""
    kb_id: str = Field(..., description="知识库ID")


class RunMindmapRequest(BaseModel):
    """运行Mindmap请求模型"""
    kb_id: str = Field(..., description="知识库ID")


class ListPipelineLogsRequest(BaseModel):
    """列出管道日志请求模型"""
    operation_status: Optional[List[str]] = Field([], description="操作状态列表")
    types: Optional[List[str]] = Field([], description="文件类型列表")
    suffix: Optional[List[str]] = Field([], description="文件后缀列表")


class ListPipelineDatasetLogsRequest(BaseModel):
    """列出管道数据集日志请求模型"""
    operation_status: Optional[List[str]] = Field([], description="操作状态列表")


class DeletePipelineLogsRequest(BaseModel):
    """删除管道日志请求模型"""
    log_ids: List[str] = Field(..., description="日志ID列表")


class UnbindTaskRequest(BaseModel):
    """解绑任务请求模型"""
    kb_id: str = Field(..., description="知识库ID")
    pipeline_task_type: str = Field(..., description="管道任务类型")
