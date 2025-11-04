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

from typing import Optional
from pydantic import BaseModel, Field


class SetApiKeyRequest(BaseModel):
    """设置 API Key 请求"""
    llm_factory: str = Field(..., description="LLM 工厂名称")
    api_key: str = Field(..., description="API Key")
    base_url: Optional[str] = Field(default="", description="API Base URL")
    model_type: Optional[str] = Field(default=None, description="模型类型")
    llm_name: Optional[str] = Field(default=None, description="LLM 名称")


class AddLLMRequest(BaseModel):
    """添加 LLM 请求"""
    llm_factory: str = Field(..., description="LLM 工厂名称")
    model_type: str = Field(..., description="模型类型")
    llm_name: str = Field(..., description="LLM 名称")
    api_key: Optional[str] = Field(default="x", description="API Key")
    api_base: Optional[str] = Field(default="", description="API Base URL")
    max_tokens: Optional[int] = Field(default=None, description="最大 Token 数")
    
    # VolcEngine 特殊字段
    ark_api_key: Optional[str] = None
    endpoint_id: Optional[str] = None
    
    # Tencent Hunyuan 特殊字段
    hunyuan_sid: Optional[str] = None
    hunyuan_sk: Optional[str] = None
    
    # Tencent Cloud 特殊字段
    tencent_cloud_sid: Optional[str] = None
    tencent_cloud_sk: Optional[str] = None
    
    # Bedrock 特殊字段
    bedrock_ak: Optional[str] = None
    bedrock_sk: Optional[str] = None
    bedrock_region: Optional[str] = None
    
    # XunFei Spark 特殊字段
    spark_api_password: Optional[str] = None
    spark_app_id: Optional[str] = None
    spark_api_secret: Optional[str] = None
    spark_api_key: Optional[str] = None
    
    # BaiduYiyan 特殊字段
    yiyan_ak: Optional[str] = None
    yiyan_sk: Optional[str] = None
    
    # Fish Audio 特殊字段
    fish_audio_ak: Optional[str] = None
    fish_audio_refid: Optional[str] = None
    
    # Google Cloud 特殊字段
    google_project_id: Optional[str] = None
    google_region: Optional[str] = None
    google_service_account_key: Optional[str] = None
    
    # Azure-OpenAI 特殊字段
    api_version: Optional[str] = None
    
    # OpenRouter 特殊字段
    provider_order: Optional[str] = None


class DeleteLLMRequest(BaseModel):
    """删除 LLM 请求"""
    llm_factory: str = Field(..., description="LLM 工厂名称")
    llm_name: str = Field(..., description="LLM 名称")


class DeleteFactoryRequest(BaseModel):
    """删除工厂请求"""
    llm_factory: str = Field(..., description="LLM 工厂名称")


class MyLLMsQuery(BaseModel):
    """获取我的 LLMs 查询参数"""
    include_details: Optional[str] = Field(default="false", description="是否包含详细信息")


class ListLLMsQuery(BaseModel):
    """列出 LLMs 查询参数"""
    model_type: Optional[str] = Field(default=None, description="模型类型过滤")

