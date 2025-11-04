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
from typing import Optional, List

from fastapi import APIRouter, Depends, Query, UploadFile, File, Form
from fastapi.responses import Response

from api.apps.models.auth_dependencies import get_current_user
from api.apps.models.document_models import (
    CreateDocumentRequest,
    WebCrawlRequest,
    ListDocumentsQuery,
    ListDocumentsBody,
    FilterDocumentsRequest,
    GetDocumentInfosRequest,
    ChangeStatusRequest,
    DeleteDocumentRequest,
    RunDocumentRequest,
    RenameDocumentRequest,
    ChangeParserRequest,
    ChangeParserSimpleRequest,
    UploadAndParseRequest,
    ParseRequest,
    SetMetaRequest,
)
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
)
from api.utils.file_utils import filename_type, get_project_base_directory, thumbnail
from api.utils.web_utils import CONTENT_TYPE_MAP, html2pdf, is_valid_url
from deepdoc.parser.html_parser import RAGFlowHtmlParser
from rag.nlp import search, rag_tokenizer
from rag.utils.storage_factory import STORAGE_IMPL

# 创建路由器
router = APIRouter()


@router.post("/upload")
async def upload(
    kb_id: str = Form(...),
    files: List[UploadFile] = File(...),
    current_user = Depends(get_current_user)
):
    """上传文档"""
    if not files:
        return get_json_result(data=False, message="No file part!", code=settings.RetCode.ARGUMENT_ERROR)
    
    for file_obj in files:
        if not file_obj.filename or file_obj.filename == "":
            return get_json_result(data=False, message="No file selected!", code=settings.RetCode.ARGUMENT_ERROR)
        if len(file_obj.filename.encode("utf-8")) > FILE_NAME_LEN_LIMIT:
            return get_json_result(data=False, message=f"File name must be {FILE_NAME_LEN_LIMIT} bytes or less.", code=settings.RetCode.ARGUMENT_ERROR)

    e, kb = KnowledgebaseService.get_by_id(kb_id)
    if not e:
        raise LookupError("Can't find this knowledgebase!")
    if not check_kb_team_permission(kb, current_user.id):
        return get_json_result(data=False, message="No authorization.", code=settings.RetCode.AUTHENTICATION_ERROR)

    err, uploaded_files = FileService.upload_document(kb, files, current_user.id)
    if err:
        return get_json_result(data=uploaded_files, message="\n".join(err), code=settings.RetCode.SERVER_ERROR)

    if not uploaded_files:
        return get_json_result(data=uploaded_files, message="There seems to be an issue with your file format. Please verify it is correct and not corrupted.", code=settings.RetCode.DATA_ERROR)
    files_result = [f[0] for f in uploaded_files]  # remove the blob

    return get_json_result(data=files_result)


@router.post("/web_crawl")
async def web_crawl(
    request: WebCrawlRequest,
    current_user = Depends(get_current_user)
):
    """网页爬取"""
    kb_id = request.kb_id
    name = request.name
    url = request.url
    
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
            "pipeline_id": kb.pipeline_id,
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
    request: CreateDocumentRequest,
    current_user = Depends(get_current_user)
):
    """创建文档"""
    req = request.model_dump(exclude_unset=True)
    kb_id = req["kb_id"]
    
    if len(req["name"].encode("utf-8")) > FILE_NAME_LEN_LIMIT:
        return get_json_result(data=False, message=f"File name must be {FILE_NAME_LEN_LIMIT} bytes or less.", code=settings.RetCode.ARGUMENT_ERROR)

    if req["name"].strip() == "":
        return get_json_result(data=False, message="File name can't be empty.", code=settings.RetCode.ARGUMENT_ERROR)
    req["name"] = req["name"].strip()

    try:
        e, kb = KnowledgebaseService.get_by_id(kb_id)
        if not e:
            return get_data_error_result(message="Can't find this knowledgebase!")

        if DocumentService.query(name=req["name"], kb_id=kb_id):
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
                "name": req["name"],
                "suffix": Path(req["name"]).suffix.lstrip("."),
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
    query: ListDocumentsQuery = Depends(),
    body: Optional[ListDocumentsBody] = None,
    current_user = Depends(get_current_user)
):
    """列出文档"""
    if body is None:
        body = ListDocumentsBody()
    
    kb_id = query.kb_id
    tenants = UserTenantService.query(user_id=current_user.id)
    for tenant in tenants:
        if KnowledgebaseService.query(tenant_id=tenant.tenant_id, id=kb_id):
            break
    else:
        return get_json_result(data=False, message="Only owner of knowledgebase authorized for this operation.", code=settings.RetCode.OPERATING_ERROR)
    
    keywords = query.keywords or ""
    page_number = int(query.page or 0)
    items_per_page = int(query.page_size or 0)
    orderby = query.orderby or "create_time"
    desc = query.desc.lower() == "true" if query.desc else True
    create_time_from = int(query.create_time_from or 0)
    create_time_to = int(query.create_time_to or 0)

    run_status = body.run_status or []
    if run_status:
        invalid_status = {s for s in run_status if s not in VALID_TASK_STATUS}
        if invalid_status:
            return get_data_error_result(message=f"Invalid filter run status conditions: {', '.join(invalid_status)}")

    types = body.types or []
    if types:
        invalid_types = {t for t in types if t not in VALID_FILE_TYPES}
        if invalid_types:
            return get_data_error_result(message=f"Invalid filter conditions: {', '.join(invalid_types)} type{'s' if len(invalid_types) > 1 else ''}")

    suffix = body.suffix or []

    try:
        docs, tol = DocumentService.get_by_kb_id(kb_id, page_number, items_per_page, orderby, desc, keywords, run_status, types, suffix)

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
    request: FilterDocumentsRequest,
    current_user = Depends(get_current_user)
):
    """过滤文档"""
    kb_id = request.kb_id
    tenants = UserTenantService.query(user_id=current_user.id)
    for tenant in tenants:
        if KnowledgebaseService.query(tenant_id=tenant.tenant_id, id=kb_id):
            break
    else:
        return get_json_result(data=False, message="Only owner of knowledgebase authorized for this operation.", code=settings.RetCode.OPERATING_ERROR)

    keywords = request.keywords or ""
    suffix = request.suffix or []
    run_status = request.run_status or []
    
    if run_status:
        invalid_status = {s for s in run_status if s not in VALID_TASK_STATUS}
        if invalid_status:
            return get_data_error_result(message=f"Invalid filter run status conditions: {', '.join(invalid_status)}")

    types = request.types or []
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
    request: GetDocumentInfosRequest,
    current_user = Depends(get_current_user)
):
    """获取文档信息"""
    doc_ids = request.doc_ids
    for doc_id in doc_ids:
        if not DocumentService.accessible(doc_id, current_user.id):
            return get_json_result(data=False, message="No authorization.", code=settings.RetCode.AUTHENTICATION_ERROR)
    docs = DocumentService.get_by_ids(doc_ids)
    return get_json_result(data=list(docs.dicts()))


@router.get("/thumbnails")
async def thumbnails(
    doc_ids: List[str] = Query(..., description="文档ID列表"),
):
    """获取文档缩略图"""
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
    request: ChangeStatusRequest,
    current_user = Depends(get_current_user)
):
    """修改文档状态"""
    doc_ids = request.doc_ids
    status = request.status

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
    request: DeleteDocumentRequest,
    current_user = Depends(get_current_user)
):
    """删除文档"""
    doc_ids = request.doc_id
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
    request: RunDocumentRequest,
    current_user = Depends(get_current_user)
):
    """运行文档解析"""
    for doc_id in request.doc_ids:
        if not DocumentService.accessible(doc_id, current_user.id):
            return get_json_result(data=False, message="No authorization.", code=settings.RetCode.AUTHENTICATION_ERROR)
    
    try:
        kb_table_num_map = {}
        for id in request.doc_ids:
            info = {"run": str(request.run), "progress": 0}
            if str(request.run) == TaskStatus.RUNNING.value and request.delete:
                info["progress_msg"] = ""
                info["chunk_num"] = 0
                info["token_num"] = 0

            tenant_id = DocumentService.get_tenant_id(id)
            if not tenant_id:
                return get_data_error_result(message="Tenant not found!")
            e, doc = DocumentService.get_by_id(id)
            if not e:
                return get_data_error_result(message="Document not found!")

            if str(request.run) == TaskStatus.CANCEL.value:
                if str(doc.run) == TaskStatus.RUNNING.value:
                    cancel_all_task_of(id)
                else:
                    return get_data_error_result(message="Cannot cancel a task that is not in RUNNING status")
            if all([not request.delete, str(request.run) == TaskStatus.RUNNING.value, str(doc.run) == TaskStatus.DONE.value]):
                DocumentService.clear_chunk_num_when_rerun(doc.id)

            DocumentService.update_by_id(id, info)
            if request.delete:
                TaskService.filter_delete([Task.doc_id == id])
                if settings.docStoreConn.indexExist(search.index_name(tenant_id), doc.kb_id):
                    settings.docStoreConn.delete({"doc_id": id}, search.index_name(tenant_id), doc.kb_id)

            if str(request.run) == TaskStatus.RUNNING.value:
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
    request: RenameDocumentRequest,
    current_user = Depends(get_current_user)
):
    """重命名文档"""
    if not DocumentService.accessible(request.doc_id, current_user.id):
        return get_json_result(data=False, message="No authorization.", code=settings.RetCode.AUTHENTICATION_ERROR)
    
    try:
        e, doc = DocumentService.get_by_id(request.doc_id)
        if not e:
            return get_data_error_result(message="Document not found!")
        if pathlib.Path(request.name.lower()).suffix != pathlib.Path(doc.name.lower()).suffix:
            return get_json_result(data=False, message="The extension of file can't be changed", code=settings.RetCode.ARGUMENT_ERROR)
        if len(request.name.encode("utf-8")) > FILE_NAME_LEN_LIMIT:
            return get_json_result(data=False, message=f"File name must be {FILE_NAME_LEN_LIMIT} bytes or less.", code=settings.RetCode.ARGUMENT_ERROR)

        for d in DocumentService.query(name=request.name, kb_id=doc.kb_id):
            if d.name == request.name:
                return get_data_error_result(message="Duplicated document name in the same knowledgebase.")

        if not DocumentService.update_by_id(request.doc_id, {"name": request.name}):
            return get_data_error_result(message="Database error (Document rename)!")

        informs = File2DocumentService.get_by_document_id(request.doc_id)
        if informs:
            e, file = FileService.get_by_id(informs[0].file_id)
            FileService.update_by_id(file.id, {"name": request.name})

        tenant_id = DocumentService.get_tenant_id(request.doc_id)
        title_tks = rag_tokenizer.tokenize(request.name)
        es_body = {
            "docnm_kwd": request.name,
            "title_tks": title_tks,
            "title_sm_tks": rag_tokenizer.fine_grained_tokenize(title_tks),
        }
        if settings.docStoreConn.indexExist(search.index_name(tenant_id), doc.kb_id):
            settings.docStoreConn.update(
                {"doc_id": request.doc_id},
                es_body,
                search.index_name(tenant_id),
                doc.kb_id,
            )

        return get_json_result(data=True)
    except Exception as e:
        return server_error_response(e)


@router.get("/get/{doc_id}")
async def get(doc_id: str):
    """获取文档文件"""
    try:
        e, doc = DocumentService.get_by_id(doc_id)
        if not e:
            return get_data_error_result(message="Document not found!")

        b, n = File2DocumentService.get_storage_address(doc_id=doc_id)
        content = STORAGE_IMPL.get(b, n)

        ext = re.search(r"\.([^.]+)$", doc.name.lower())
        ext = ext.group(1) if ext else None
        content_type = "application/octet-stream"
        if ext:
            if doc.type == FileType.VISUAL.value:
                content_type = CONTENT_TYPE_MAP.get(ext, f"image/{ext}")
            else:
                content_type = CONTENT_TYPE_MAP.get(ext, f"application/{ext}")
        
        return Response(content=content, media_type=content_type)
    except Exception as e:
        return server_error_response(e)


@router.post("/change_parser")
async def change_parser(
    request: ChangeParserSimpleRequest,
    current_user = Depends(get_current_user)
):
    """修改文档解析器"""
    if not DocumentService.accessible(request.doc_id, current_user.id):
        return get_json_result(data=False, message="No authorization.", code=settings.RetCode.AUTHENTICATION_ERROR)

    e, doc = DocumentService.get_by_id(request.doc_id)
    if not e:
        return get_data_error_result(message="Document not found!")

    def reset_doc(update_data_override=None):
        nonlocal doc
        update_data = update_data_override or {}
        if request.pipeline_id is not None:
            update_data["pipeline_id"] = request.pipeline_id
        if request.parser_id is not None:
            update_data["parser_id"] = request.parser_id
        update_data.update({
            "progress": 0,
            "progress_msg": "",
            "run": TaskStatus.UNSTART.value
        })
        e = DocumentService.update_by_id(doc.id, update_data)
        if not e:
            return get_data_error_result(message="Document not found!")
        if doc.token_num > 0:
            e = DocumentService.increment_chunk_num(doc.id, doc.kb_id, doc.token_num * -1, doc.chunk_num * -1, doc.process_duration * -1)
            if not e:
                return get_data_error_result(message="Document not found!")
            tenant_id = DocumentService.get_tenant_id(request.doc_id)
            if not tenant_id:
                return get_data_error_result(message="Tenant not found!")
            if settings.docStoreConn.indexExist(search.index_name(tenant_id), doc.kb_id):
                settings.docStoreConn.delete({"doc_id": doc.id}, search.index_name(tenant_id), doc.kb_id)

    try:
        if request.pipeline_id is not None and request.pipeline_id != "":
            if doc.pipeline_id == request.pipeline_id:
                return get_json_result(data=True)
            reset_doc({"pipeline_id": request.pipeline_id})
            return get_json_result(data=True)

        if request.parser_id is None:
            return get_json_result(data=False, message="缺少 parser_id 或 pipeline_id", code=settings.RetCode.ARGUMENT_ERROR)

        if doc.parser_id.lower() == request.parser_id.lower():
            if request.parser_config is not None:
                if request.parser_config == doc.parser_config:
                    return get_json_result(data=True)
            else:
                return get_json_result(data=True)

        if (doc.type == FileType.VISUAL and request.parser_id != "picture") or (re.search(r"\.(ppt|pptx|pages)$", doc.name) and request.parser_id != "presentation"):
            return get_data_error_result(message="Not supported yet!")
        
        if request.parser_config is not None:
            DocumentService.update_parser_config(doc.id, request.parser_config)
        
        reset_doc()
        return get_json_result(data=True)
    except Exception as e:
        return server_error_response(e)


@router.get("/image/{image_id}")
async def get_image(image_id: str):
    """获取图片"""
    try:
        arr = image_id.split("-")
        if len(arr) != 2:
            return get_data_error_result(message="Image not found.")
        bkt, nm = image_id.split("-")
        content = STORAGE_IMPL.get(bkt, nm)
        return Response(content=content, media_type="image/JPEG")
    except Exception as e:
        return server_error_response(e)


@router.post("/upload_and_parse")
async def upload_and_parse(
    conversation_id: str = Form(...),
    files: List[UploadFile] = File(...),
    current_user = Depends(get_current_user)
):
    """上传并解析"""
    if not files:
        return get_json_result(data=False, message="No file part!", code=settings.RetCode.ARGUMENT_ERROR)

    for file_obj in files:
        if not file_obj.filename or file_obj.filename == "":
            return get_json_result(data=False, message="No file selected!", code=settings.RetCode.ARGUMENT_ERROR)

    doc_ids = doc_upload_and_parse(conversation_id, files, current_user.id)

    return get_json_result(data=doc_ids)


@router.post("/parse")
async def parse(
    request: Optional[ParseRequest] = None,
    files: Optional[List[UploadFile]] = File(None),
    current_user = Depends(get_current_user)
):
    """解析文档"""
    url = request.url if request else None
    
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

    txt = FileService.parse_docs(files, current_user.id)

    return get_json_result(data=txt)


@router.post("/set_meta")
async def set_meta(
    request: SetMetaRequest,
    current_user = Depends(get_current_user)
):
    """设置元数据"""
    if not DocumentService.accessible(request.doc_id, current_user.id):
        return get_json_result(data=False, message="No authorization.", code=settings.RetCode.AUTHENTICATION_ERROR)
    
    try:
        meta = json.loads(request.meta)
        
        e, doc = DocumentService.get_by_id(request.doc_id)
        if not e:
            return get_data_error_result(message="Document not found!")

        if not DocumentService.update_by_id(request.doc_id, {"meta_fields": meta}):
            return get_data_error_result(message="Database error (meta updates)!")

        return get_json_result(data=True)
    except Exception as e:
        return server_error_response(e)

