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
#  limitations under the License
#

from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from api.db.services.file2document_service import File2DocumentService
from api.db.services.file_service import FileService

from api.db.services.knowledgebase_service import KnowledgebaseService
from api.utils.api_utils import server_error_response, get_data_error_result, validate_request
from api.utils import get_uuid
from api.db import FileType
from api.db.services.document_service import DocumentService
from api import settings
from api.utils.api_utils import get_json_result
from pydantic import BaseModel

# Security
security = HTTPBearer()

# Pydantic models for request/response
class ConvertRequest(BaseModel):
    file_ids: List[str]
    kb_ids: List[str]

class RemoveFile2DocumentRequest(BaseModel):
    file_ids: List[str]

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


@router.post('/convert')
async def convert(
    req: ConvertRequest,
    current_user = Depends(get_current_user)
):
    kb_ids = req.kb_ids
    file_ids = req.file_ids
    file2documents = []

    try:
        files = FileService.get_by_ids(file_ids)
        files_set = dict({file.id: file for file in files})
        for file_id in file_ids:
            file = files_set[file_id]
            if not file:
                return get_data_error_result(message="File not found!")
            file_ids_list = [file_id]
            if file.type == FileType.FOLDER.value:
                file_ids_list = FileService.get_all_innermost_file_ids(file_id, [])
            for id in file_ids_list:
                informs = File2DocumentService.get_by_file_id(id)
                # delete
                for inform in informs:
                    doc_id = inform.document_id
                    e, doc = DocumentService.get_by_id(doc_id)
                    if not e:
                        return get_data_error_result(message="Document not found!")
                    tenant_id = DocumentService.get_tenant_id(doc_id)
                    if not tenant_id:
                        return get_data_error_result(message="Tenant not found!")
                    if not DocumentService.remove_document(doc, tenant_id):
                        return get_data_error_result(
                            message="Database error (Document removal)!")
                File2DocumentService.delete_by_file_id(id)

                # insert
                for kb_id in kb_ids:
                    e, kb = KnowledgebaseService.get_by_id(kb_id)
                    if not e:
                        return get_data_error_result(
                            message="Can't find this knowledgebase!")
                    e, file = FileService.get_by_id(id)
                    if not e:
                        return get_data_error_result(
                            message="Can't find this file!")

                    doc = DocumentService.insert({
                        "id": get_uuid(),
                        "kb_id": kb.id,
                        "parser_id": FileService.get_parser(file.type, file.name, kb.parser_id),
                        "parser_config": kb.parser_config,
                        "created_by": current_user.id,
                        "type": file.type,
                        "name": file.name,
                        "suffix": Path(file.name).suffix.lstrip("."),
                        "location": file.location,
                        "size": file.size
                    })
                    file2document = File2DocumentService.insert({
                        "id": get_uuid(),
                        "file_id": id,
                        "document_id": doc.id,
                    })

                    file2documents.append(file2document.to_json())
        return get_json_result(data=file2documents)
    except Exception as e:
        return server_error_response(e)


@router.post('/rm')
async def rm(
    req: RemoveFile2DocumentRequest,
    current_user = Depends(get_current_user)
):
    file_ids = req.file_ids
    if not file_ids:
        return get_json_result(
            data=False, message='Lack of "Files ID"', code=settings.RetCode.ARGUMENT_ERROR)
    try:
        for file_id in file_ids:
            informs = File2DocumentService.get_by_file_id(file_id)
            if not informs:
                return get_data_error_result(message="Inform not found!")
            for inform in informs:
                if not inform:
                    return get_data_error_result(message="Inform not found!")
                File2DocumentService.delete_by_file_id(file_id)
                doc_id = inform.document_id
                e, doc = DocumentService.get_by_id(doc_id)
                if not e:
                    return get_data_error_result(message="Document not found!")
                tenant_id = DocumentService.get_tenant_id(doc_id)
                if not tenant_id:
                    return get_data_error_result(message="Tenant not found!")
                if not DocumentService.remove_document(doc, tenant_id):
                    return get_data_error_result(
                        message="Database error (Document removal)!")
        return get_json_result(data=True)
    except Exception as e:
        return server_error_response(e)
