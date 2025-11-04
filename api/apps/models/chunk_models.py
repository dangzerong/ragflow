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

from typing import Optional, List, Any, Union
from pydantic import BaseModel, Field, field_validator


class ListChunksRequest(BaseModel):
    """列出文档块请求"""
    doc_id: str = Field(..., description="文档ID")
    page: Optional[int] = Field(default=1, description="页码")
    size: Optional[int] = Field(default=30, description="每页大小")
    keywords: Optional[str] = Field(default="", description="关键词")
    available_int: Optional[int] = Field(default=None, description="可用状态")


class SetChunkRequest(BaseModel):
    """设置文档块请求"""
    doc_id: str = Field(..., description="文档ID")
    chunk_id: str = Field(..., description="块ID")
    content_with_weight: str = Field(..., description="内容")
    important_kwd: Optional[List[str]] = Field(default=None, description="重要关键词列表")
    question_kwd: Optional[List[str]] = Field(default=None, description="问题关键词列表")
    tag_kwd: Optional[str] = Field(default=None, description="标签关键词")
    tag_feas: Optional[Any] = Field(default=None, description="标签特征")
    available_int: Optional[int] = Field(default=None, description="可用状态")


class SwitchChunksRequest(BaseModel):
    """切换文档块状态请求"""
    doc_id: str = Field(..., description="文档ID")
    chunk_ids: List[str] = Field(..., description="块ID列表")
    available_int: int = Field(..., description="可用状态")


class DeleteChunksRequest(BaseModel):
    """删除文档块请求"""
    doc_id: str = Field(..., description="文档ID")
    chunk_ids: List[str] = Field(..., description="块ID列表")


class CreateChunkRequest(BaseModel):
    """创建文档块请求"""
    doc_id: str = Field(..., description="文档ID")
    content_with_weight: str = Field(..., description="内容")
    important_kwd: Optional[List[str]] = Field(default=[], description="重要关键词列表")
    question_kwd: Optional[List[str]] = Field(default=[], description="问题关键词列表")
    tag_feas: Optional[Any] = Field(default=None, description="标签特征")


class RetrievalTestRequest(BaseModel):
    """检索测试请求"""
    kb_id: Union[str, List[str]] = Field(..., description="知识库ID，可以是字符串或列表")
    question: str = Field(..., description="问题")
    page: Optional[int] = Field(default=1, description="页码")
    size: Optional[int] = Field(default=30, description="每页大小")
    doc_ids: Optional[List[str]] = Field(default=[], description="文档ID列表")
    use_kg: Optional[bool] = Field(default=False, description="是否使用知识图谱")
    top_k: Optional[int] = Field(default=1024, description="Top K")
    cross_languages: Optional[List[str]] = Field(default=[], description="跨语言列表")
    search_id: Optional[str] = Field(default="", description="搜索ID")
    rerank_id: Optional[str] = Field(default=None, description="重排序模型ID")
    keyword: Optional[bool] = Field(default=False, description="是否使用关键词")
    similarity_threshold: Optional[float] = Field(default=0.0, description="相似度阈值")
    vector_similarity_weight: Optional[float] = Field(default=0.3, description="向量相似度权重")
    highlight: Optional[bool] = Field(default=False, description="是否高亮")

