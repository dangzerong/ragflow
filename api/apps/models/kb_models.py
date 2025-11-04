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

from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, model_validator


class CreateKnowledgeBaseRequest(BaseModel):
    """创建知识库请求
    
    支持两种解析类型：
    - parse_type=1: 使用内置解析器，需要 parser_id，pipeline_id 为空
    - parse_type=2: 使用自定义 pipeline，需要 pipeline_id，parser_id 为空
    """
    name: str
    parse_type: Literal[1, 2] = Field(..., description="解析类型：1=内置解析器，2=自定义pipeline")
    embd_id: str = Field(..., description="嵌入模型ID")
    parser_id: Optional[str] = Field(default="", description="解析器ID，parse_type=1时必需")
    pipeline_id: Optional[str] = Field(default="", description="流水线ID，parse_type=2时必需")
    description: Optional[str] = None
    pagerank: Optional[int] = None
    
    @model_validator(mode='after')
    def validate_parse_type_fields(self):
        """根据 parse_type 验证相应字段"""
        if self.parse_type == 1:
            # parse_type=1: 需要 parser_id，pipeline_id 必须为空
            parser_id_val = self.parser_id or ""
            pipeline_id_val = self.pipeline_id or ""
            
            if parser_id_val.strip() == "":
                raise ValueError("parse_type=1时，parser_id不能为空")
            if pipeline_id_val.strip() != "":
                raise ValueError("parse_type=1时，pipeline_id必须为空")
        elif self.parse_type == 2:
            # parse_type=2: 需要 pipeline_id，parser_id 必须为空
            parser_id_val = self.parser_id or ""
            pipeline_id_val = self.pipeline_id or ""
            
            if pipeline_id_val.strip() == "":
                raise ValueError("parse_type=2时，pipeline_id不能为空")
            if parser_id_val.strip() != "":
                raise ValueError("parse_type=2时，parser_id必须为空")
        return self


class UpdateKnowledgeBaseRequest(BaseModel):
    """更新知识库请求"""
    kb_id: str
    name: str
    description: str
    parser_id: str
    pagerank: Optional[int] = None
    # 其他可选字段，但排除 id, tenant_id, created_by, create_time, update_time, create_date, update_date


class DeleteKnowledgeBaseRequest(BaseModel):
    """删除知识库请求"""
    kb_id: str


class ListKnowledgeBasesQuery(BaseModel):
    """列出知识库查询参数"""
    keywords: Optional[str] = ""
    page: Optional[int] = 0
    page_size: Optional[int] = 0
    parser_id: Optional[str] = None
    orderby: Optional[str] = "create_time"
    desc: Optional[str] = "true"


class ListKnowledgeBasesBody(BaseModel):
    """列出知识库请求体"""
    owner_ids: Optional[List[str]] = []


class RemoveTagsRequest(BaseModel):
    """删除标签请求"""
    tags: List[str]


class RenameTagRequest(BaseModel):
    """重命名标签请求"""
    from_tag: str
    to_tag: str


class ListPipelineLogsQuery(BaseModel):
    """列出流水线日志查询参数"""
    kb_id: str
    keywords: Optional[str] = ""
    page: Optional[int] = 0
    page_size: Optional[int] = 0
    orderby: Optional[str] = "create_time"
    desc: Optional[str] = "true"
    create_date_from: Optional[str] = ""
    create_date_to: Optional[str] = ""


class ListPipelineLogsBody(BaseModel):
    """列出流水线日志请求体"""
    operation_status: Optional[List[str]] = []
    types: Optional[List[str]] = []
    suffix: Optional[List[str]] = []


class ListPipelineDatasetLogsQuery(BaseModel):
    """列出流水线数据集日志查询参数"""
    kb_id: str
    page: Optional[int] = 0
    page_size: Optional[int] = 0
    orderby: Optional[str] = "create_time"
    desc: Optional[str] = "true"
    create_date_from: Optional[str] = ""
    create_date_to: Optional[str] = ""


class ListPipelineDatasetLogsBody(BaseModel):
    """列出流水线数据集日志请求体"""
    operation_status: Optional[List[str]] = []


class DeletePipelineLogsQuery(BaseModel):
    """删除流水线日志查询参数"""
    kb_id: str


class DeletePipelineLogsBody(BaseModel):
    """删除流水线日志请求体"""
    log_ids: List[str]


class RunGraphragRequest(BaseModel):
    """运行 GraphRAG 请求"""
    kb_id: str


class RunRaptorRequest(BaseModel):
    """运行 RAPTOR 请求"""
    kb_id: str


class RunMindmapRequest(BaseModel):
    """运行 Mindmap 请求"""
    kb_id: str

