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
import json
import os.path
import pathlib
import re
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Query
from fastapi.responses import StreamingResponse

from api import settings
from api.common.check_team_permission import check_kb_team_permission
from api.constants import FILE_NAME_LEN_LIMIT, IMG_BASE64_PREFIX
from api.db import VALID_FILE_TYPES, VALID_TASK_STATUS, FileSource, FileType, ParserType, TaskStatus
from api.db.db_models import File, Task
from api.db.services import duplicate_name
from api.db.services.document_service import DocumentService, doc_upload_and_parse
from api.db.services.file2document_service import File2DocumentService
from api.db.services.file_service import FileService
from api.db.services.knowledgebase_service import KnowledgebaseService
from api.db.services.task_service import TaskService, cancel_all_task_of, queue_tasks, queue_dataflow
from api.db.services.user_service import UserTenantService
from api.utils import get_uuid
from api.utils.api_utils import (
    get_data_error_result,
    get_json_result,
    server_error_response,
    validate_request,
)
from api.utils.file_utils import filename_type, get_project_base_directory, thumbnail
from api.utils.web_utils import CONTENT_TYPE_MAP, html2pdf, is_valid_url
from deepdoc.parser.html_parser import RAGFlowHtmlParser
from rag.nlp import search
from rag.utils.storage_factory import STORAGE_IMPL
from pydantic import BaseModel
from api.db.db_models import User

# Pydantic models for request/response
class WebCrawlRequest(BaseModel):
    kb_id: str
    name: str
    url: str

class CreateDocumentRequest(BaseModel):
    name: str
    kb_id: str

class DocumentListRequest(BaseModel):
    run_status: List[str] = []
    types: List[str] = []
    suffix: List[str] = []

class DocumentFilterRequest(BaseModel):
    kb_id: str
    keywords: str = ""
    run_status: List[str] = []
    types: List[str] = []
    suffix: List[str] = []

class DocumentInfosRequest(BaseModel):
    doc_ids: List[str]

class ChangeStatusRequest(BaseModel):
    doc_ids: List[str]
    status: str

class RemoveDocumentRequest(BaseModel):
    doc_id: List[str]

class RunDocumentRequest(BaseModel):
    doc_ids: List[str]
    run: str
    delete: bool = False

class RenameDocumentRequest(BaseModel):
    doc_id: str
    name: str

class ChangeParserRequest(BaseModel):
    doc_id: str
    parser_id: str
    pipeline_id: Optional[str] = None
    parser_config: Optional[dict] = None

class UploadAndParseRequest(BaseModel):
    conversation_id: str

class ParseRequest(BaseModel):
    url: Optional[str] = None

class SetMetaRequest(BaseModel):
    doc_id: str
    meta: str

# File wrapper for compatibility
class FileWrapper:
    def __init__(self, upload_file: UploadFile):
        self.filename = upload_file.filename
        self.file = upload_file.file
        self.content_type = upload_file.content_type
    
    def read(self):
        return self.file.read()
    
    def save(self, path):
        with open(path, "wb") as f:
            f.write(self.file.read())

# Dependency injection
async def get_current_user():
    # This should be implemented based on your authentication system
    # For now, returning a mock user
    from api.db.db_models import User
    return User(id="current_user_id", tenant_id="tenant_id")

# Create router
router = APIRouter(prefix="/v1/document", tags=["document"])


@router.post("/upload")
async def upload(
    kb_id: str = Form(...),
    files: List[UploadFile] = File(...),
    current_user = Depends(get_current_user)
):
    if not kb_id:
        return get_json_result(data=False, message='Lack of "KB ID"', code=settings.RetCode.ARGUMENT_ERROR)
    
    if not files:
        return get_json_result(data=False, message="No file part!", code=settings.RetCode.ARGUMENT_ERROR)

    # Convert UploadFile to FileWrapper for compatibility
    file_objs = [FileWrapper(file) for file in files]
    
    for file_obj in file_objs:
        if file_obj.filename == "":
            return get_json_result(data=False, message="No file selected!", code=settings.RetCode.ARGUMENT_ERROR)
        if len(file_obj.filename.encode("utf-8")) > FILE_NAME_LEN_LIMIT:
            return get_json_result(data=False, message=f"File name must be {FILE_NAME_LEN_LIMIT} bytes or less.", code=settings.RetCode.ARGUMENT_ERROR)

    e, kb = KnowledgebaseService.get_by_id(kb_id)
    if not e:
        raise LookupError("Can't find this knowledgebase!")
    if not check_kb_team_permission(kb, current_user.id):
        return get_json_result(data=False, message="No authorization.", code=settings.RetCode.AUTHENTICATION_ERROR)

    err, files = FileService.upload_document(kb, file_objs, current_user.id)
    if err:
        return get_json_result(data=files, message="\n".join(err), code=settings.RetCode.SERVER_ERROR)

    if not files:
        return get_json_result(data=files, message="There seems to be an issue with your file format. Please verify it is correct and not corrupted.", code=settings.RetCode.DATA_ERROR)
    files = [f[0] for f in files]  # remove the blob

    return get_json_result(data=files)


@router.post("/web_crawl")
async def web_crawl(
    req: WebCrawlRequest,
    current_user = Depends(get_current_user)
):
    kb_id = req.kb_id
    if not kb_id:
        return get_json_result(data=False, message='Lack of "KB ID"', code=settings.RetCode.ARGUMENT_ERROR)
    name = req.name
    url = req.url
    if not is_valid_url(url):
        return get_json_result(data=False, message="The URL format is invalid", code=settings.RetCode.ARGUMENT_ERROR)
    e, kb = KnowledgebaseService.get_by_id(kb_id)
    if not e:
        raise LookupError("Can't find this knowledgebase!")
    if not check_kb_team_permission(kb, current_user.id):
        return get_json_result(data=False, message="No authorization.", code=settings.RetCode.AUTHENTICATION_ERROR)

    blob = html2pdf(url)
    if not blob:
        return server_error_response(ValueError("Download failure."))

    root_folder = FileService.get_root_folder(current_user.id)
    pf_id = root_folder["id"]
    FileService.init_knowledgebase_docs(pf_id, current_user.id)
    kb_root_folder = FileService.get_kb_folder(current_user.id)
    kb_folder = FileService.new_a_file_from_kb(kb.tenant_id, kb.name, kb_root_folder["id"])

    try:
        filename = duplicate_name(DocumentService.query, name=name + ".pdf", kb_id=kb.id)
        filetype = filename_type(filename)
        if filetype == FileType.OTHER.value:
            raise RuntimeError("This type of file has not been supported yet!")

        location = filename
        while STORAGE_IMPL.obj_exist(kb_id, location):
            location += "_"
        STORAGE_IMPL.put(kb_id, location, blob)
        doc = {
            "id": get_uuid(),
            "kb_id": kb.id,
            "parser_id": kb.parser_id,
            "parser_config": kb.parser_config,
            "created_by": current_user.id,
            "type": filetype,
            "name": filename,
            "location": location,
            "size": len(blob),
            "thumbnail": thumbnail(filename, blob),
            "suffix": Path(filename).suffix.lstrip("."),
        }
        if doc["type"] == FileType.VISUAL:
            doc["parser_id"] = ParserType.PICTURE.value
        if doc["type"] == FileType.AURAL:
            doc["parser_id"] = ParserType.AUDIO.value
        if re.search(r"\.(ppt|pptx|pages)$", filename):
            doc["parser_id"] = ParserType.PRESENTATION.value
        if re.search(r"\.(eml)$", filename):
            doc["parser_id"] = ParserType.EMAIL.value
        DocumentService.insert(doc)
        FileService.add_file_from_kb(doc, kb_folder["id"], kb.tenant_id)
    except Exception as e:
        return server_error_response(e)
    return get_json_result(data=True)


@router.post("/create")
async def create(
    req: CreateDocumentRequest,
    current_user = Depends(get_current_user)
):
    kb_id = req.kb_id
    if not kb_id:
        return get_json_result(data=False, message='Lack of "KB ID"', code=settings.RetCode.ARGUMENT_ERROR)
    if len(req.name.encode("utf-8")) > FILE_NAME_LEN_LIMIT:
        return get_json_result(data=False, message=f"File name must be {FILE_NAME_LEN_LIMIT} bytes or less.", code=settings.RetCode.ARGUMENT_ERROR)

    if req.name.strip() == "":
        return get_json_result(data=False, message="File name can't be empty.", code=settings.RetCode.ARGUMENT_ERROR)
    req.name = req.name.strip()

    try:
        e, kb = KnowledgebaseService.get_by_id(kb_id)
        if not e:
            return get_data_error_result(message="Can't find this knowledgebase!")

        if DocumentService.query(name=req.name, kb_id=kb_id):
            return get_data_error_result(message="Duplicated document name in the same knowledgebase.")

        kb_root_folder = FileService.get_kb_folder(kb.tenant_id)
        if not kb_root_folder:
            return get_data_error_result(message="Cannot find the root folder.")
        kb_folder = FileService.new_a_file_from_kb(
            kb.tenant_id,
            kb.name,
            kb_root_folder["id"],
        )
        if not kb_folder:
            return get_data_error_result(message="Cannot find the kb folder for this file.")

        doc = DocumentService.insert(
            {
                "id": get_uuid(),
                "kb_id": kb.id,
                "parser_id": kb.parser_id,
                "pipeline_id": kb.pipeline_id,
                "parser_config": kb.parser_config,
                "created_by": current_user.id,
                "type": FileType.VIRTUAL,
                "name": req.name,
                "suffix": Path(req.name).suffix.lstrip("."),
                "location": "",
                "size": 0,
            }
        )

        FileService.add_file_from_kb(doc.to_dict(), kb_folder["id"], kb.tenant_id)

        return get_json_result(data=doc.to_json())
    except Exception as e:
        return server_error_response(e)


@router.post("/list")
async def list_docs(
    kb_id: str = Query(...),
    keywords: str = Query(""),
    page: int = Query(0),
    page_size: int = Query(0),
    orderby: str = Query("create_time"),
    desc: str = Query("true"),
    create_time_from: int = Query(0),
    create_time_to: int = Query(0),
    req: DocumentListRequest = None,
    current_user = Depends(get_current_user)
):
    if not kb_id:
        return get_json_result(data=False, message='Lack of "KB ID"', code=settings.RetCode.ARGUMENT_ERROR)
    tenants = UserTenantService.query(user_id=current_user.id)
    for tenant in tenants:
        if KnowledgebaseService.query(tenant_id=tenant.tenant_id, id=kb_id):
            break
    else:
        return get_json_result(data=False, message="Only owner of knowledgebase authorized for this operation.", code=settings.RetCode.OPERATING_ERROR)

    if desc.lower() == "false":
        desc_bool = False
    else:
        desc_bool = True

    run_status = req.run_status if req else []
    if run_status:
        invalid_status = {s for s in run_status if s not in VALID_TASK_STATUS}
        if invalid_status:
            return get_data_error_result(message=f"Invalid filter run status conditions: {', '.join(invalid_status)}")

    types = req.types if req else []
    if types:
        invalid_types = {t for t in types if t not in VALID_FILE_TYPES}
        if invalid_types:
            return get_data_error_result(message=f"Invalid filter conditions: {', '.join(invalid_types)} type{'s' if len(invalid_types) > 1 else ''}")

    suffix = req.suffix if req else []

    try:
        docs, tol = DocumentService.get_by_kb_id(kb_id, page, page_size, orderby, desc_bool, keywords, run_status, types, suffix)

        if create_time_from or create_time_to:
            filtered_docs = []
            for doc in docs:
                doc_create_time = doc.get("create_time", 0)
                if (create_time_from == 0 or doc_create_time >= create_time_from) and (create_time_to == 0 or doc_create_time <= create_time_to):
                    filtered_docs.append(doc)
            docs = filtered_docs

        for doc_item in docs:
            if doc_item["thumbnail"] and not doc_item["thumbnail"].startswith(IMG_BASE64_PREFIX):
                doc_item["thumbnail"] = f"/v1/document/image/{kb_id}-{doc_item['thumbnail']}"

        return get_json_result(data={"total": tol, "docs": docs})
    except Exception as e:
        return server_error_response(e)


@router.post("/filter")
async def get_filter(
    req: DocumentFilterRequest,
    current_user = Depends(get_current_user)
):
    kb_id = req.kb_id
    if not kb_id:
        return get_json_result(data=False, message='Lack of "KB ID"', code=settings.RetCode.ARGUMENT_ERROR)
    tenants = UserTenantService.query(user_id=current_user.id)
    for tenant in tenants:
        if KnowledgebaseService.query(tenant_id=tenant.tenant_id, id=kb_id):
            break
    else:
        return get_json_result(data=False, message="Only owner of knowledgebase authorized for this operation.", code=settings.RetCode.OPERATING_ERROR)

    keywords = req.keywords
    suffix = req.suffix
    run_status = req.run_status
    if run_status:
        invalid_status = {s for s in run_status if s not in VALID_TASK_STATUS}
        if invalid_status:
            return get_data_error_result(message=f"Invalid filter run status conditions: {', '.join(invalid_status)}")

    types = req.types
    if types:
        invalid_types = {t for t in types if t not in VALID_FILE_TYPES}
        if invalid_types:
            return get_data_error_result(message=f"Invalid filter conditions: {', '.join(invalid_types)} type{'s' if len(invalid_types) > 1 else ''}")

    try:
        filter, total = DocumentService.get_filter_by_kb_id(kb_id, keywords, run_status, types, suffix)
        return get_json_result(data={"total": total, "filter": filter})
    except Exception as e:
        return server_error_response(e)


@router.post("/infos")
async def docinfos(
    req: DocumentInfosRequest,
    current_user = Depends(get_current_user)
):
    doc_ids = req.doc_ids
    for doc_id in doc_ids:
        if not DocumentService.accessible(doc_id, current_user.id):
            return get_json_result(data=False, message="No authorization.", code=settings.RetCode.AUTHENTICATION_ERROR)
    docs = DocumentService.get_by_ids(doc_ids)
    return get_json_result(data=list(docs.dicts()))


@router.get("/thumbnails")
async def thumbnails(
    doc_ids: List[str] = Query(...)
):
    if not doc_ids:
        return get_json_result(data=False, message='Lack of "Document ID"', code=settings.RetCode.ARGUMENT_ERROR)

    try:
        docs = DocumentService.get_thumbnails(doc_ids)

        for doc_item in docs:
            if doc_item["thumbnail"] and not doc_item["thumbnail"].startswith(IMG_BASE64_PREFIX):
                doc_item["thumbnail"] = f"/v1/document/image/{doc_item['kb_id']}-{doc_item['thumbnail']}"

        return get_json_result(data={d["id"]: d["thumbnail"] for d in docs})
    except Exception as e:
        return server_error_response(e)


@router.post("/change_status")
async def change_status(
    req: ChangeStatusRequest,
    current_user = Depends(get_current_user)
):
    doc_ids = req.doc_ids
    status = str(req.status)

    if status not in ["0", "1"]:
        return get_json_result(data=False, message='"Status" must be either 0 or 1!', code=settings.RetCode.ARGUMENT_ERROR)

    result = {}
    for doc_id in doc_ids:
        if not DocumentService.accessible(doc_id, current_user.id):
            result[doc_id] = {"error": "No authorization."}
            continue

        try:
            e, doc = DocumentService.get_by_id(doc_id)
            if not e:
                result[doc_id] = {"error": "No authorization."}
                continue
            e, kb = KnowledgebaseService.get_by_id(doc.kb_id)
            if not e:
                result[doc_id] = {"error": "Can't find this knowledgebase!"}
                continue
            if not DocumentService.update_by_id(doc_id, {"status": str(status)}):
                result[doc_id] = {"error": "Database error (Document update)!"}
                continue

            status_int = int(status)
            if not settings.docStoreConn.update({"doc_id": doc_id}, {"available_int": status_int}, search.index_name(kb.tenant_id), doc.kb_id):
                result[doc_id] = {"error": "Database error (docStore update)!"}
            result[doc_id] = {"status": status}
        except Exception as e:
            result[doc_id] = {"error": f"Internal server error: {str(e)}"}

    return get_json_result(data=result)


@router.post("/rm")
async def rm(
    req: RemoveDocumentRequest,
    current_user = Depends(get_current_user)
):
    doc_ids = req.doc_id
    if isinstance(doc_ids, str):
        doc_ids = [doc_ids]

    for doc_id in doc_ids:
        if not DocumentService.accessible4deletion(doc_id, current_user.id):
            return get_json_result(data=False, message="No authorization.", code=settings.RetCode.AUTHENTICATION_ERROR)

    root_folder = FileService.get_root_folder(current_user.id)
    pf_id = root_folder["id"]
    FileService.init_knowledgebase_docs(pf_id, current_user.id)
    errors = ""
    kb_table_num_map = {}
    for doc_id in doc_ids:
        try:
            e, doc = DocumentService.get_by_id(doc_id)
            if not e:
                return get_data_error_result(message="Document not found!")
            tenant_id = DocumentService.get_tenant_id(doc_id)
            if not tenant_id:
                return get_data_error_result(message="Tenant not found!")

            b, n = File2DocumentService.get_storage_address(doc_id=doc_id)

            TaskService.filter_delete([Task.doc_id == doc_id])
            if not DocumentService.remove_document(doc, tenant_id):
                return get_data_error_result(message="Database error (Document removal)!")

            f2d = File2DocumentService.get_by_document_id(doc_id)
            deleted_file_count = 0
            if f2d:
                deleted_file_count = FileService.filter_delete([File.source_type == FileSource.KNOWLEDGEBASE, File.id == f2d[0].file_id])
            File2DocumentService.delete_by_document_id(doc_id)
            if deleted_file_count > 0:
                STORAGE_IMPL.rm(b, n)

            doc_parser = doc.parser_id
            if doc_parser == ParserType.TABLE:
                kb_id = doc.kb_id
                if kb_id not in kb_table_num_map:
                    counts = DocumentService.count_by_kb_id(kb_id=kb_id, keywords="", run_status=[TaskStatus.DONE], types=[])
                    kb_table_num_map[kb_id] = counts
                kb_table_num_map[kb_id] -= 1
                if kb_table_num_map[kb_id] <= 0:
                    KnowledgebaseService.delete_field_map(kb_id)
        except Exception as e:
            errors += str(e)

    if errors:
        return get_json_result(data=False, message=errors, code=settings.RetCode.SERVER_ERROR)

    return get_json_result(data=True)


@router.post("/run")
async def run(
    req: RunDocumentRequest,
    current_user = Depends(get_current_user)
):
    for doc_id in req.doc_ids:
        if not DocumentService.accessible(doc_id, current_user.id):
            return get_json_result(data=False, message="No authorization.", code=settings.RetCode.AUTHENTICATION_ERROR)
    try:
        kb_table_num_map = {}
        for id in req.doc_ids:
            info = {"run": str(req.run), "progress": 0}
            if str(req.run) == TaskStatus.RUNNING.value and req.delete:
                info["progress_msg"] = ""
                info["chunk_num"] = 0
                info["token_num"] = 0

            tenant_id = DocumentService.get_tenant_id(id)
            if not tenant_id:
                return get_data_error_result(message="Tenant not found!")
            e, doc = DocumentService.get_by_id(id)
            if not e:
                return get_data_error_result(message="Document not found!")

            if str(req.run) == TaskStatus.CANCEL.value:
                if str(doc.run) == TaskStatus.RUNNING.value:
                    cancel_all_task_of(id)
                else:
                    return get_data_error_result(message="Cannot cancel a task that is not in RUNNING status")
            if all([req.delete, str(req.run) == TaskStatus.RUNNING.value, str(doc.run) == TaskStatus.DONE.value]):
                DocumentService.clear_chunk_num_when_rerun(doc.id)

            DocumentService.update_by_id(id, info)
            if req.delete:
                TaskService.filter_delete([Task.doc_id == id])
                if settings.docStoreConn.indexExist(search.index_name(tenant_id), doc.kb_id):
                    settings.docStoreConn.delete({"doc_id": id}, search.index_name(tenant_id), doc.kb_id)

            if str(req.run) == TaskStatus.RUNNING.value:
                doc = doc.to_dict()
                doc["tenant_id"] = tenant_id

                doc_parser = doc.get("parser_id", ParserType.NAIVE)
                if doc_parser == ParserType.TABLE:
                    kb_id = doc.get("kb_id")
                    if not kb_id:
                        continue
                    if kb_id not in kb_table_num_map:
                        count = DocumentService.count_by_kb_id(kb_id=kb_id, keywords="", run_status=[TaskStatus.DONE], types=[])
                        kb_table_num_map[kb_id] = count
                        if kb_table_num_map[kb_id] <= 0:
                            KnowledgebaseService.delete_field_map(kb_id)
                if doc.get("pipeline_id", ""):
                    queue_dataflow(tenant_id, flow_id=doc["pipeline_id"], task_id=get_uuid(), doc_id=id)
                else:
                    bucket, name = File2DocumentService.get_storage_address(doc_id=doc["id"])
                    queue_tasks(doc, bucket, name, 0)

        return get_json_result(data=True)
    except Exception as e:
        return server_error_response(e)


@router.post("/rename")
async def rename(
    req: RenameDocumentRequest,
    current_user = Depends(get_current_user)
):
    if not DocumentService.accessible(req.doc_id, current_user.id):
        return get_json_result(data=False, message="No authorization.", code=settings.RetCode.AUTHENTICATION_ERROR)
    try:
        e, doc = DocumentService.get_by_id(req.doc_id)
        if not e:
            return get_data_error_result(message="Document not found!")
        if pathlib.Path(req.name.lower()).suffix != pathlib.Path(doc.name.lower()).suffix:
            return get_json_result(data=False, message="The extension of file can't be changed", code=settings.RetCode.ARGUMENT_ERROR)
        if len(req.name.encode("utf-8")) > FILE_NAME_LEN_LIMIT:
            return get_json_result(data=False, message=f"File name must be {FILE_NAME_LEN_LIMIT} bytes or less.", code=settings.RetCode.ARGUMENT_ERROR)

        for d in DocumentService.query(name=req.name, kb_id=doc.kb_id):
            if d.name == req.name:
                return get_data_error_result(message="Duplicated document name in the same knowledgebase.")

        if not DocumentService.update_by_id(req.doc_id, {"name": req.name}):
            return get_data_error_result(message="Database error (Document rename)!")

        informs = File2DocumentService.get_by_document_id(req.doc_id)
        if informs:
            e, file = FileService.get_by_id(informs[0].file_id)
            FileService.update_by_id(file.id, {"name": req.name})

        return get_json_result(data=True)
    except Exception as e:
        return server_error_response(e)


@router.get("/get/{doc_id}")
async def get(doc_id: str):
    try:
        e, doc = DocumentService.get_by_id(doc_id)
        if not e:
            return get_data_error_result(message="Document not found!")

        b, n = File2DocumentService.get_storage_address(doc_id=doc_id)
        content = STORAGE_IMPL.get(b, n)

        ext = re.search(r"\.([^.]+)$", doc.name.lower())
        ext = ext.group(1) if ext else None
        
        if ext:
            if doc.type == FileType.VISUAL.value:
                media_type = CONTENT_TYPE_MAP.get(ext, f"image/{ext}")
            else:
                media_type = CONTENT_TYPE_MAP.get(ext, f"application/{ext}")
        else:
            media_type = "application/octet-stream"
            
        return StreamingResponse(
            iter([content]),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={doc.name}"}
        )
    except Exception as e:
        return server_error_response(e)


@router.post("/change_parser")
async def change_parser(
    req: ChangeParserRequest,
    current_user = Depends(get_current_user)
):
    if not DocumentService.accessible(req.doc_id, current_user.id):
        return get_json_result(data=False, message="No authorization.", code=settings.RetCode.AUTHENTICATION_ERROR)

    e, doc = DocumentService.get_by_id(req.doc_id)
    if not e:
        return get_data_error_result(message="Document not found!")

    def reset_doc():
        nonlocal doc
        e = DocumentService.update_by_id(doc.id, {"parser_id": req.parser_id, "progress": 0, "progress_msg": "", "run": TaskStatus.UNSTART.value})
        if not e:
            return get_data_error_result(message="Document not found!")
        if doc.token_num > 0:
            e = DocumentService.increment_chunk_num(doc.id, doc.kb_id, doc.token_num * -1, doc.chunk_num * -1, doc.process_duration * -1)
            if not e:
                return get_data_error_result(message="Document not found!")
            tenant_id = DocumentService.get_tenant_id(req.doc_id)
            if not tenant_id:
                return get_data_error_result(message="Tenant not found!")
            if settings.docStoreConn.indexExist(search.index_name(tenant_id), doc.kb_id):
                settings.docStoreConn.delete({"doc_id": doc.id}, search.index_name(tenant_id), doc.kb_id)

    try:
        if req.pipeline_id:
            if doc.pipeline_id == req.pipeline_id:
                return get_json_result(data=True)
            DocumentService.update_by_id(doc.id, {"pipeline_id": req.pipeline_id})
            reset_doc()
            return get_json_result(data=True)

        if doc.parser_id.lower() == req.parser_id.lower():
            if req.parser_config:
                if req.parser_config == doc.parser_config:
                    return get_json_result(data=True)
            else:
                return get_json_result(data=True)

        if (doc.type == FileType.VISUAL and req.parser_id != "picture") or (re.search(r"\.(ppt|pptx|pages)$", doc.name) and req.parser_id != "presentation"):
            return get_data_error_result(message="Not supported yet!")
        if req.parser_config:
            DocumentService.update_parser_config(doc.id, req.parser_config)
        reset_doc()
        return get_json_result(data=True)
    except Exception as e:
        return server_error_response(e)


@router.get("/image/{image_id}")
async def get_image(image_id: str):
    try:
        arr = image_id.split("-")
        if len(arr) != 2:
            return get_data_error_result(message="Image not found.")
        bkt, nm = image_id.split("-")
        content = STORAGE_IMPL.get(bkt, nm)
        return StreamingResponse(
            iter([content]),
            media_type="image/JPEG"
        )
    except Exception as e:
        return server_error_response(e)


@router.post("/upload_and_parse")
async def upload_and_parse(
    conversation_id: str = Form(...),
    files: List[UploadFile] = File(...),
    current_user = Depends(get_current_user)
):
    if not files:
        return get_json_result(data=False, message="No file part!", code=settings.RetCode.ARGUMENT_ERROR)

    # Convert UploadFile to FileWrapper for compatibility
    file_objs = [FileWrapper(file) for file in files]
    
    for file_obj in file_objs:
        if file_obj.filename == "":
            return get_json_result(data=False, message="No file selected!", code=settings.RetCode.ARGUMENT_ERROR)

    doc_ids = doc_upload_and_parse(conversation_id, file_objs, current_user.id)

    return get_json_result(data=doc_ids)


@router.post("/parse")
async def parse(
    req: ParseRequest = None,
    files: List[UploadFile] = File(None),
    current_user = Depends(get_current_user)
):
    url = req.url if req else ""
    if url:
        if not is_valid_url(url):
            return get_json_result(data=False, message="The URL format is invalid", code=settings.RetCode.ARGUMENT_ERROR)
        download_path = os.path.join(get_project_base_directory(), "logs/downloads")
        os.makedirs(download_path, exist_ok=True)
        from seleniumwire.webdriver import Chrome, ChromeOptions

        options = ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_experimental_option("prefs", {"download.default_directory": download_path, "download.prompt_for_download": False, "download.directory_upgrade": True, "safebrowsing.enabled": True})
        driver = Chrome(options=options)
        driver.get(url)
        res_headers = [r.response.headers for r in driver.requests if r and r.response]
        if len(res_headers) > 1:
            sections = RAGFlowHtmlParser().parser_txt(driver.page_source)
            driver.quit()
            return get_json_result(data="\n".join(sections))

        class File:
            filename: str
            filepath: str

            def __init__(self, filename, filepath):
                self.filename = filename
                self.filepath = filepath

            def read(self):
                with open(self.filepath, "rb") as f:
                    return f.read()

        r = re.search(r"filename=\"([^\"]+)\"", str(res_headers))
        if not r or not r.group(1):
            return get_json_result(data=False, message="Can't not identify downloaded file", code=settings.RetCode.ARGUMENT_ERROR)
        f = File(r.group(1), os.path.join(download_path, r.group(1)))
        txt = FileService.parse_docs([f], current_user.id)
        return get_json_result(data=txt)

    if not files:
        return get_json_result(data=False, message="No file part!", code=settings.RetCode.ARGUMENT_ERROR)

    # Convert UploadFile to FileWrapper for compatibility
    file_objs = [FileWrapper(file) for file in files]
    txt = FileService.parse_docs(file_objs, current_user.id)

    return get_json_result(data=txt)


@router.post("/set_meta")
async def set_meta(
    req: SetMetaRequest,
    current_user = Depends(get_current_user)
):
    if not DocumentService.accessible(req.doc_id, current_user.id):
        return get_json_result(data=False, message="No authorization.", code=settings.RetCode.AUTHENTICATION_ERROR)
    try:
        meta = json.loads(req.meta)
        if not isinstance(meta, dict):
            return get_json_result(data=False, message="Only dictionary type supported.", code=settings.RetCode.ARGUMENT_ERROR)
        for k, v in meta.items():
            if not isinstance(v, str) and not isinstance(v, int) and not isinstance(v, float):
                return get_json_result(data=False, message=f"The type is not supported: {v}", code=settings.RetCode.ARGUMENT_ERROR)
    except Exception as e:
        return get_json_result(data=False, message=f"Json syntax error: {e}", code=settings.RetCode.ARGUMENT_ERROR)
    if not isinstance(meta, dict):
        return get_json_result(data=False, message='Meta data should be in Json map format, like {"key": "value"}', code=settings.RetCode.ARGUMENT_ERROR)

    try:
        e, doc = DocumentService.get_by_id(req.doc_id)
        if not e:
            return get_data_error_result(message="Document not found!")

        if not DocumentService.update_by_id(req.doc_id, {"meta_fields": meta}):
            return get_data_error_result(message="Database error (meta updates)!")

        return get_json_result(data=True)
    except Exception as e:
        return server_error_response(e)
