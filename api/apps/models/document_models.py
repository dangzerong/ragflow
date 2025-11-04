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

from typing import Optional, Literal, List
from pydantic import BaseModel, Field, model_validator


class CreateDocumentRequest(BaseModel):
    """创建文档请求
    
    支持两种解析类型：
    - parse_type=1: 使用内置解析器，需要 parser_id，pipeline_id 为空
    - parse_type=2: 使用自定义 pipeline，需要 pipeline_id，parser_id 为空
    如果不提供 parse_type，则从知识库继承解析配置
    """
    name: str
    kb_id: str
    parse_type: Optional[Literal[1, 2]] = Field(default=None, description="解析类型：1=内置解析器，2=自定义pipeline，None=从知识库继承")
    parser_id: Optional[str] = Field(default="", description="解析器ID，parse_type=1时必需")
    pipeline_id: Optional[str] = Field(default="", description="流水线ID，parse_type=2时必需")
    parser_config: Optional[dict] = None

    @model_validator(mode='after')
    def validate_parse_type_fields(self):
        """根据 parse_type 验证相应字段"""
        if self.parse_type is not None:
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


class ChangeParserRequest(BaseModel):
    """修改文档解析器请求
    
    支持两种解析类型：
    - parse_type=1: 使用内置解析器，需要 parser_id，pipeline_id 为空
    - parse_type=2: 使用自定义 pipeline，需要 pipeline_id，parser_id 为空
    """
    doc_id: str
    parse_type: Literal[1, 2] = Field(..., description="解析类型：1=内置解析器，2=自定义pipeline")
    parser_id: Optional[str] = Field(default="", description="解析器ID，parse_type=1时必需")
    pipeline_id: Optional[str] = Field(default="", description="流水线ID，parse_type=2时必需")
    parser_config: Optional[dict] = None

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


class WebCrawlRequest(BaseModel):
    """网页爬取请求"""
    kb_id: str
    name: str
    url: str


class ListDocumentsQuery(BaseModel):
    """列出文档查询参数"""
    kb_id: str
    keywords: Optional[str] = ""
    page: Optional[int] = 0
    page_size: Optional[int] = 0
    orderby: Optional[str] = "create_time"
    desc: Optional[str] = "true"
    create_time_from: Optional[int] = 0
    create_time_to: Optional[int] = 0


class ListDocumentsBody(BaseModel):
    """列出文档请求体"""
    run_status: Optional[List[str]] = []
    types: Optional[List[str]] = []
    suffix: Optional[List[str]] = []


class FilterDocumentsRequest(BaseModel):
    """过滤文档请求"""
    kb_id: str
    keywords: Optional[str] = ""
    suffix: Optional[List[str]] = []
    run_status: Optional[List[str]] = []
    types: Optional[List[str]] = []


class GetDocumentInfosRequest(BaseModel):
    """获取文档信息请求"""
    doc_ids: List[str]


class ChangeStatusRequest(BaseModel):
    """修改文档状态请求"""
    doc_ids: List[str]
    status: str  # "0" 或 "1"

    @model_validator(mode='after')
    def validate_status(self):
        if self.status not in ["0", "1"]:
            raise ValueError('Status must be either 0 or 1!')
        return self


class DeleteDocumentRequest(BaseModel):
    """删除文档请求"""
    doc_id: str | List[str]  # 支持单个或列表


class RunDocumentRequest(BaseModel):
    """运行文档解析请求"""
    doc_ids: List[str]
    run: str  # TaskStatus 值
    delete: Optional[bool] = False


class RenameDocumentRequest(BaseModel):
    """重命名文档请求"""
    doc_id: str
    name: str


class ChangeParserSimpleRequest(BaseModel):
    """简单修改解析器请求（兼容旧逻辑）"""
    doc_id: str
    parser_id: Optional[str] = None
    pipeline_id: Optional[str] = None
    parser_config: Optional[dict] = None


class UploadAndParseRequest(BaseModel):
    """上传并解析请求（仅用于验证 conversation_id）"""
    conversation_id: str


class ParseRequest(BaseModel):
    """解析请求"""
    url: Optional[str] = None


class SetMetaRequest(BaseModel):
    """设置元数据请求"""
    doc_id: str
    meta: str  # JSON 字符串

    @model_validator(mode='after')
    def validate_meta(self):
        import json
        try:
            meta_dict = json.loads(self.meta)
            if not isinstance(meta_dict, dict):
                raise ValueError("Only dictionary type supported.")
            for k, v in meta_dict.items():
                if not isinstance(v, (str, int, float)):
                    raise ValueError(f"The type is not supported: {v}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Json syntax error: {e}")
        return self

