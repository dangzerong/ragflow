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
import json
import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse

from api.models.kb_models import (
    CreateKnowledgeBaseRequest,
    UpdateKnowledgeBaseRequest,
    DeleteKnowledgeBaseRequest,
    ListKnowledgeBasesRequest,
    RemoveTagsRequest,
    RenameTagRequest,
    RunGraphRAGRequest,
    RunRaptorRequest,
    RunMindmapRequest,
    ListPipelineLogsRequest,
    ListPipelineDatasetLogsRequest,
    DeletePipelineLogsRequest,
    UnbindTaskRequest
)
from api.utils.api_utils import get_current_user

from api.db.services import duplicate_name
from api.db.services.document_service import DocumentService, queue_raptor_o_graphrag_tasks
from api.db.services.file2document_service import File2DocumentService
from api.db.services.file_service import FileService
from api.db.services.pipeline_operation_log_service import PipelineOperationLogService
from api.db.services.task_service import TaskService, GRAPH_RAPTOR_FAKE_DOC_ID
from api.db.services.user_service import TenantService, UserTenantService
from api.utils.api_utils import get_error_data_result, server_error_response, get_data_error_result, get_json_result
from api.utils import get_uuid
from api.db import PipelineTaskType, StatusEnum, FileSource, VALID_FILE_TYPES, VALID_TASK_STATUS
from api.db.services.knowledgebase_service import KnowledgebaseService
from api.db.db_models import File
from api import settings
from rag.nlp import search
from api.constants import DATASET_NAME_LIMIT
from rag.settings import PAGERANK_FLD
from rag.utils.storage_factory import STORAGE_IMPL

# 创建 FastAPI 路由器
router = APIRouter()


@router.post('/create')
async def create(
    request: CreateKnowledgeBaseRequest,
    current_user = Depends(get_current_user)
):
    dataset_name = request.name
    if not isinstance(dataset_name, str):
        return get_data_error_result(message="Dataset name must be string.")
    if dataset_name.strip() == "":
        return get_data_error_result(message="Dataset name can't be empty.")
    if len(dataset_name.encode("utf-8")) > DATASET_NAME_LIMIT:
        return get_data_error_result(
            message=f"Dataset name length is {len(dataset_name)} which is larger than {DATASET_NAME_LIMIT}")

    dataset_name = dataset_name.strip()
    dataset_name = duplicate_name(
        KnowledgebaseService.query,
        name=dataset_name,
        tenant_id=current_user.id,
        status=StatusEnum.VALID.value)
    try:
        req = {
            "id": get_uuid(),
            "name": dataset_name,
            "tenant_id": current_user.id,
            "created_by": current_user.id,
            "parser_id": request.parser_id or "naive",
            "description": request.description
        }
        e, t = TenantService.get_by_id(current_user.id)
        if not e:
            return get_data_error_result(message="Tenant not found.")
        
        # 设置 embd_id 默认值
        if not request.embd_id:
            req["embd_id"] = t.embd_id
        else:
            req["embd_id"] = request.embd_id
            
        if request.parser_config:
            req["parser_config"] = request.parser_config
        else:
            req["parser_config"] = {
                "layout_recognize": "DeepDOC",
                "chunk_token_num": 512,
                "delimiter": "\n",
                "auto_keywords": 0,
                "auto_questions": 0,
                "html4excel": False,
                "topn_tags": 3,
                "raptor": {
                    "use_raptor": True,
                    "prompt": "Please summarize the following paragraphs. Be careful with the numbers, do not make things up. Paragraphs as following:\n      {cluster_content}\nThe above is the content you need to summarize.",
                    "max_token": 256,
                    "threshold": 0.1,
                    "max_cluster": 64,
                    "random_seed": 0
                },
                "graphrag": {
                    "use_graphrag": True,
                    "entity_types": [
                        "organization",
                        "person",
                        "geo",
                        "event",
                        "category"
                    ],
                    "method": "light"
                }
            }
        if not KnowledgebaseService.save(**req):
            return get_data_error_result()
        return get_json_result(data={"kb_id": req["id"]})
    except Exception as e:
        return server_error_response(e)


@router.post('/update')
async def update(
    request: UpdateKnowledgeBaseRequest,
    current_user = Depends(get_current_user)
):
    if not isinstance(request.name, str):
        return get_data_error_result(message="Dataset name must be string.")
    if request.name.strip() == "":
        return get_data_error_result(message="Dataset name can't be empty.")
    if len(request.name.encode("utf-8")) > DATASET_NAME_LIMIT:
        return get_data_error_result(
            message=f"Dataset name length is {len(request.name)} which is large than {DATASET_NAME_LIMIT}")
    name = request.name.strip()

    if not KnowledgebaseService.accessible4deletion(request.kb_id, current_user.id):
        return get_json_result(
            data=False,
            message='No authorization.',
            code=settings.RetCode.AUTHENTICATION_ERROR
        )
    try:
        if not KnowledgebaseService.query(
                created_by=current_user.id, id=request.kb_id):
            return get_json_result(
                data=False, message='Only owner of knowledgebase authorized for this operation.',
                code=settings.RetCode.OPERATING_ERROR)

        e, kb = KnowledgebaseService.get_by_id(request.kb_id)
        if not e:
            return get_data_error_result(
                message="Can't find this knowledgebase!")

        if name.lower() != kb.name.lower() \
                and len(
            KnowledgebaseService.query(name=name, tenant_id=current_user.id, status=StatusEnum.VALID.value)) >= 1:
            return get_data_error_result(
                message="Duplicated knowledgebase name.")

        update_data = {
            "name": name,
            "pagerank": request.pagerank
        }
        if not KnowledgebaseService.update_by_id(kb.id, update_data):
            return get_data_error_result()

        if kb.pagerank != request.pagerank:
            if request.pagerank > 0:
                settings.docStoreConn.update({"kb_id": kb.id}, {PAGERANK_FLD: request.pagerank},
                                         search.index_name(kb.tenant_id), kb.id)
            else:
                # Elasticsearch requires PAGERANK_FLD be non-zero!
                settings.docStoreConn.update({"exists": PAGERANK_FLD}, {"remove": PAGERANK_FLD},
                                         search.index_name(kb.tenant_id), kb.id)

        e, kb = KnowledgebaseService.get_by_id(kb.id)
        if not e:
            return get_data_error_result(
                message="Database error (Knowledgebase rename)!")
        kb = kb.to_dict()
        kb.update(update_data)

        return get_json_result(data=kb)
    except Exception as e:
        return server_error_response(e)


@router.get('/detail')
async def detail(
    kb_id: str = Query(..., description="知识库ID"),
    current_user = Depends(get_current_user)
):
    try:
        tenants = UserTenantService.query(user_id=current_user.id)
        for tenant in tenants:
            if KnowledgebaseService.query(
                    tenant_id=tenant.tenant_id, id=kb_id):
                break
        else:
            return get_json_result(
                data=False, message='Only owner of knowledgebase authorized for this operation.',
                code=settings.RetCode.OPERATING_ERROR)
        kb = KnowledgebaseService.get_detail(kb_id)
        if not kb:
            return get_data_error_result(
                message="Can't find this knowledgebase!")
        kb["size"] = DocumentService.get_total_size_by_kb_id(kb_id=kb["id"],keywords="", run_status=[], types=[])
        return get_json_result(data=kb)
    except Exception as e:
        return server_error_response(e)


@router.post('/list')
async def list_kbs(
    request: ListKnowledgeBasesRequest,
    keywords: str = Query("", description="关键词"),
    page: int = Query(0, description="页码"),
    page_size: int = Query(0, description="每页大小"),
    parser_id: Optional[str] = Query(None, description="解析器ID"),
    orderby: str = Query("create_time", description="排序字段"),
    desc: bool = Query(True, description="是否降序"),
    current_user = Depends(get_current_user)
):
    page_number = page
    items_per_page = page_size
    owner_ids = request.owner_ids
    try:
        if not owner_ids:
            tenants = TenantService.get_joined_tenants_by_user_id(current_user.id)
            tenants = [m["tenant_id"] for m in tenants]
            kbs, total = KnowledgebaseService.get_by_tenant_ids(
                tenants, current_user.id, page_number,
                items_per_page, orderby, desc, keywords, parser_id)
        else:
            tenants = owner_ids
            kbs, total = KnowledgebaseService.get_by_tenant_ids(
                tenants, current_user.id, 0,
                0, orderby, desc, keywords, parser_id)
            kbs = [kb for kb in kbs if kb["tenant_id"] in tenants]
            total = len(kbs)
            if page_number and items_per_page:
                kbs = kbs[(page_number-1)*items_per_page:page_number*items_per_page]
        return get_json_result(data={"kbs": kbs, "total": total})
    except Exception as e:
        return server_error_response(e)

@router.post('/rm')
async def rm(
    request: DeleteKnowledgeBaseRequest,
    current_user = Depends(get_current_user)
):
    if not KnowledgebaseService.accessible4deletion(request.kb_id, current_user.id):
        return get_json_result(
            data=False,
            message='No authorization.',
            code=settings.RetCode.AUTHENTICATION_ERROR
        )
    try:
        kbs = KnowledgebaseService.query(
            created_by=current_user.id, id=request.kb_id)
        if not kbs:
            return get_json_result(
                data=False, message='Only owner of knowledgebase authorized for this operation.',
                code=settings.RetCode.OPERATING_ERROR)

        for doc in DocumentService.query(kb_id=request.kb_id):
            if not DocumentService.remove_document(doc, kbs[0].tenant_id):
                return get_data_error_result(
                    message="Database error (Document removal)!")
            f2d = File2DocumentService.get_by_document_id(doc.id)
            if f2d:
                FileService.filter_delete([File.source_type == FileSource.KNOWLEDGEBASE, File.id == f2d[0].file_id])
            File2DocumentService.delete_by_document_id(doc.id)
        FileService.filter_delete(
            [File.source_type == FileSource.KNOWLEDGEBASE, File.type == "folder", File.name == kbs[0].name])
        if not KnowledgebaseService.delete_by_id(request.kb_id):
            return get_data_error_result(
                message="Database error (Knowledgebase removal)!")
        for kb in kbs:
            settings.docStoreConn.delete({"kb_id": kb.id}, search.index_name(kb.tenant_id), kb.id)
            settings.docStoreConn.deleteIdx(search.index_name(kb.tenant_id), kb.id)
            if hasattr(STORAGE_IMPL, 'remove_bucket'):
                STORAGE_IMPL.remove_bucket(kb.id)
        return get_json_result(data=True)
    except Exception as e:
        return server_error_response(e)


@router.get('/{kb_id}/tags')
async def list_tags(
    kb_id: str,
    current_user = Depends(get_current_user)
):
    if not KnowledgebaseService.accessible(kb_id, current_user.id):
        return get_json_result(
            data=False,
            message='No authorization.',
            code=settings.RetCode.AUTHENTICATION_ERROR
        )

    tenants = UserTenantService.get_tenants_by_user_id(current_user.id)
    tags = []
    for tenant in tenants:
        tags += settings.retrievaler.all_tags(tenant["tenant_id"], [kb_id])
    return get_json_result(data=tags)


@router.get('/tags')
async def list_tags_from_kbs(
    kb_ids: str = Query(..., description="知识库ID列表，用逗号分隔"),
    current_user = Depends(get_current_user)
):
    kb_ids = kb_ids.split(",")
    for kb_id in kb_ids:
        if not KnowledgebaseService.accessible(kb_id, current_user.id):
            return get_json_result(
                data=False,
                message='No authorization.',
                code=settings.RetCode.AUTHENTICATION_ERROR
            )

    tenants = UserTenantService.get_tenants_by_user_id(current_user.id)
    tags = []
    for tenant in tenants:
        tags += settings.retrievaler.all_tags(tenant["tenant_id"], kb_ids)
    return get_json_result(data=tags)


@router.post('/{kb_id}/rm_tags')
async def rm_tags(
    kb_id: str,
    request: RemoveTagsRequest,
    current_user = Depends(get_current_user)
):
    if not KnowledgebaseService.accessible(kb_id, current_user.id):
        return get_json_result(
            data=False,
            message='No authorization.',
            code=settings.RetCode.AUTHENTICATION_ERROR
        )
    e, kb = KnowledgebaseService.get_by_id(kb_id)

    for t in request.tags:
        settings.docStoreConn.update({"tag_kwd": t, "kb_id": [kb_id]},
                                     {"remove": {"tag_kwd": t}},
                                     search.index_name(kb.tenant_id),
                                     kb_id)
    return get_json_result(data=True)


@router.post('/{kb_id}/rename_tag')
async def rename_tags(
    kb_id: str,
    request: RenameTagRequest,
    current_user = Depends(get_current_user)
):
    if not KnowledgebaseService.accessible(kb_id, current_user.id):
        return get_json_result(
            data=False,
            message='No authorization.',
            code=settings.RetCode.AUTHENTICATION_ERROR
        )
    e, kb = KnowledgebaseService.get_by_id(kb_id)

    settings.docStoreConn.update({"tag_kwd": request.from_tag, "kb_id": [kb_id]},
                                     {"remove": {"tag_kwd": request.from_tag.strip()}, "add": {"tag_kwd": request.to_tag}},
                                     search.index_name(kb.tenant_id),
                                     kb_id)
    return get_json_result(data=True)


@router.get('/{kb_id}/knowledge_graph')
async def knowledge_graph(
    kb_id: str,
    current_user = Depends(get_current_user)
):
    if not KnowledgebaseService.accessible(kb_id, current_user.id):
        return get_json_result(
            data=False,
            message='No authorization.',
            code=settings.RetCode.AUTHENTICATION_ERROR
        )
    _, kb = KnowledgebaseService.get_by_id(kb_id)
    req = {
        "kb_id": [kb_id],
        "knowledge_graph_kwd": ["graph"]
    }

    obj = {"graph": {}, "mind_map": {}}
    if not settings.docStoreConn.indexExist(search.index_name(kb.tenant_id), kb_id):
        return get_json_result(data=obj)
    sres = settings.retrievaler.search(req, search.index_name(kb.tenant_id), [kb_id])
    if not len(sres.ids):
        return get_json_result(data=obj)

    for id in sres.ids[:1]:
        ty = sres.field[id]["knowledge_graph_kwd"]
        try:
            content_json = json.loads(sres.field[id]["content_with_weight"])
        except Exception:
            continue

        obj[ty] = content_json

    if "nodes" in obj["graph"]:
        obj["graph"]["nodes"] = sorted(obj["graph"]["nodes"], key=lambda x: x.get("pagerank", 0), reverse=True)[:256]
        if "edges" in obj["graph"]:
            node_id_set = { o["id"] for o in obj["graph"]["nodes"] }
            filtered_edges = [o for o in obj["graph"]["edges"] if o["source"] != o["target"] and o["source"] in node_id_set and o["target"] in node_id_set]
            obj["graph"]["edges"] = sorted(filtered_edges, key=lambda x: x.get("weight", 0), reverse=True)[:128]
    return get_json_result(data=obj)


@router.delete('/{kb_id}/knowledge_graph')
async def delete_knowledge_graph(
    kb_id: str,
    current_user = Depends(get_current_user)
):
    if not KnowledgebaseService.accessible(kb_id, current_user.id):
        return get_json_result(
            data=False,
            message='No authorization.',
            code=settings.RetCode.AUTHENTICATION_ERROR
        )
    _, kb = KnowledgebaseService.get_by_id(kb_id)
    settings.docStoreConn.delete({"knowledge_graph_kwd": ["graph", "subgraph", "entity", "relation"]}, search.index_name(kb.tenant_id), kb_id)

    return get_json_result(data=True)


@router.get("/get_meta")
async def get_meta(
    kb_ids: str = Query(..., description="知识库ID列表，用逗号分隔"),
    current_user = Depends(get_current_user)
):
    kb_ids = kb_ids.split(",")
    for kb_id in kb_ids:
        if not KnowledgebaseService.accessible(kb_id, current_user.id):
            return get_json_result(
                data=False,
                message='No authorization.',
                code=settings.RetCode.AUTHENTICATION_ERROR
            )
    return get_json_result(data=DocumentService.get_meta_by_kbs(kb_ids))


@router.get("/basic_info")
async def get_basic_info(
    kb_id: str = Query(..., description="知识库ID"),
    current_user = Depends(get_current_user)
):
    if not KnowledgebaseService.accessible(kb_id, current_user.id):
        return get_json_result(
            data=False,
            message='No authorization.',
            code=settings.RetCode.AUTHENTICATION_ERROR
        )

    basic_info = DocumentService.knowledgebase_basic_info(kb_id)

    return get_json_result(data=basic_info)


@router.post("/list_pipeline_logs")
async def list_pipeline_logs(
    request: ListPipelineLogsRequest,
    kb_id: str = Query(..., description="知识库ID"),
    keywords: str = Query("", description="关键词"),
    page: int = Query(0, description="页码"),
    page_size: int = Query(0, description="每页大小"),
    orderby: str = Query("create_time", description="排序字段"),
    desc: bool = Query(True, description="是否降序"),
    create_date_from: str = Query("", description="创建日期开始"),
    create_date_to: str = Query("", description="创建日期结束"),
    current_user = Depends(get_current_user)
):
    if not kb_id:
        return get_json_result(data=False, message='Lack of "KB ID"', code=settings.RetCode.ARGUMENT_ERROR)

    page_number = page
    items_per_page = page_size
    
    if create_date_to > create_date_from:
        return get_data_error_result(message="Create data filter is abnormal.")

    operation_status = request.operation_status
    if operation_status:
        invalid_status = {s for s in operation_status if s not in VALID_TASK_STATUS}
        if invalid_status:
            return get_data_error_result(message=f"Invalid filter operation_status status conditions: {', '.join(invalid_status)}")

    types = request.types
    if types:
        invalid_types = {t for t in types if t not in VALID_FILE_TYPES}
        if invalid_types:
            return get_data_error_result(message=f"Invalid filter conditions: {', '.join(invalid_types)} type{'s' if len(invalid_types) > 1 else ''}")

    suffix = request.suffix

    try:
        logs, tol = PipelineOperationLogService.get_file_logs_by_kb_id(kb_id, page_number, items_per_page, orderby, desc, keywords, operation_status, types, suffix, create_date_from, create_date_to)
        return get_json_result(data={"total": tol, "logs": logs})
    except Exception as e:
        return server_error_response(e)


@router.post("/list_pipeline_dataset_logs")
async def list_pipeline_dataset_logs(
    request: ListPipelineDatasetLogsRequest,
    kb_id: str = Query(..., description="知识库ID"),
    page: int = Query(0, description="页码"),
    page_size: int = Query(0, description="每页大小"),
    orderby: str = Query("create_time", description="排序字段"),
    desc: bool = Query(True, description="是否降序"),
    create_date_from: str = Query("", description="创建日期开始"),
    create_date_to: str = Query("", description="创建日期结束"),
    current_user = Depends(get_current_user)
):
    if not kb_id:
        return get_json_result(data=False, message='Lack of "KB ID"', code=settings.RetCode.ARGUMENT_ERROR)

    page_number = page
    items_per_page = page_size
    
    if create_date_to > create_date_from:
        return get_data_error_result(message="Create data filter is abnormal.")

    operation_status = request.operation_status
    if operation_status:
        invalid_status = {s for s in operation_status if s not in VALID_TASK_STATUS}
        if invalid_status:
            return get_data_error_result(message=f"Invalid filter operation_status status conditions: {', '.join(invalid_status)}")

    try:
        logs, tol = PipelineOperationLogService.get_dataset_logs_by_kb_id(kb_id, page_number, items_per_page, orderby, desc, operation_status, create_date_from, create_date_to)
        return get_json_result(data={"total": tol, "logs": logs})
    except Exception as e:
        return server_error_response(e)


@router.post("/delete_pipeline_logs")
async def delete_pipeline_logs(
    request: DeletePipelineLogsRequest,
    kb_id: str = Query(..., description="知识库ID"),
    current_user = Depends(get_current_user)
):
    if not kb_id:
        return get_json_result(data=False, message='Lack of "KB ID"', code=settings.RetCode.ARGUMENT_ERROR)

    log_ids = request.log_ids

    PipelineOperationLogService.delete_by_ids(log_ids)

    return get_json_result(data=True)


@router.get("/pipeline_log_detail")
async def pipeline_log_detail(
    log_id: str = Query(..., description="日志ID"),
    current_user = Depends(get_current_user)
):
    if not log_id:
        return get_json_result(data=False, message='Lack of "Pipeline log ID"', code=settings.RetCode.ARGUMENT_ERROR)

    ok, log = PipelineOperationLogService.get_by_id(log_id)
    if not ok:
        return get_data_error_result(message="Invalid pipeline log ID")

    return get_json_result(data=log.to_dict())


@router.post("/run_graphrag")
async def run_graphrag(
    request: RunGraphRAGRequest,
    current_user = Depends(get_current_user)
):
    kb_id = request.kb_id
    if not kb_id:
        return get_error_data_result(message='Lack of "KB ID"')

    ok, kb = KnowledgebaseService.get_by_id(kb_id)
    if not ok:
        return get_error_data_result(message="Invalid Knowledgebase ID")

    task_id = kb.graphrag_task_id
    if task_id:
        ok, task = TaskService.get_by_id(task_id)
        if not ok:
            logging.warning(f"A valid GraphRAG task id is expected for kb {kb_id}")

        if task and task.progress not in [-1, 1]:
            return get_error_data_result(message=f"Task {task_id} in progress with status {task.progress}. A Graph Task is already running.")

    documents, _ = DocumentService.get_by_kb_id(
        kb_id=kb_id,
        page_number=0,
        items_per_page=0,
        orderby="create_time",
        desc=False,
        keywords="",
        run_status=[],
        types=[],
        suffix=[],
    )
    if not documents:
        return get_error_data_result(message=f"No documents in Knowledgebase {kb_id}")

    sample_document = documents[0]
    document_ids = [document["id"] for document in documents]

    task_id = queue_raptor_o_graphrag_tasks(doc=sample_document, ty="graphrag", priority=0, fake_doc_id=GRAPH_RAPTOR_FAKE_DOC_ID, doc_ids=list(document_ids))

    if not KnowledgebaseService.update_by_id(kb.id, {"graphrag_task_id": task_id}):
        logging.warning(f"Cannot save graphrag_task_id for kb {kb_id}")

    return get_json_result(data={"graphrag_task_id": task_id})


@router.get("/trace_graphrag")
async def trace_graphrag(
    kb_id: str = Query(..., description="知识库ID"),
    current_user = Depends(get_current_user)
):
    if not kb_id:
        return get_error_data_result(message='Lack of "KB ID"')

    ok, kb = KnowledgebaseService.get_by_id(kb_id)
    if not ok:
        return get_error_data_result(message="Invalid Knowledgebase ID")

    task_id = kb.graphrag_task_id
    if not task_id:
        return get_json_result(data={})

    ok, task = TaskService.get_by_id(task_id)
    if not ok:
        return get_error_data_result(message="GraphRAG Task Not Found or Error Occurred")

    return get_json_result(data=task.to_dict())


@router.post("/run_raptor")
async def run_raptor(
    request: RunRaptorRequest,
    current_user = Depends(get_current_user)
):
    kb_id = request.kb_id
    if not kb_id:
        return get_error_data_result(message='Lack of "KB ID"')

    ok, kb = KnowledgebaseService.get_by_id(kb_id)
    if not ok:
        return get_error_data_result(message="Invalid Knowledgebase ID")

    task_id = kb.raptor_task_id
    if task_id:
        ok, task = TaskService.get_by_id(task_id)
        if not ok:
            logging.warning(f"A valid RAPTOR task id is expected for kb {kb_id}")

        if task and task.progress not in [-1, 1]:
            return get_error_data_result(message=f"Task {task_id} in progress with status {task.progress}. A RAPTOR Task is already running.")

    documents, _ = DocumentService.get_by_kb_id(
        kb_id=kb_id,
        page_number=0,
        items_per_page=0,
        orderby="create_time",
        desc=False,
        keywords="",
        run_status=[],
        types=[],
        suffix=[],
    )
    if not documents:
        return get_error_data_result(message=f"No documents in Knowledgebase {kb_id}")

    sample_document = documents[0]
    document_ids = [document["id"] for document in documents]

    task_id = queue_raptor_o_graphrag_tasks(doc=sample_document, ty="raptor", priority=0, fake_doc_id=GRAPH_RAPTOR_FAKE_DOC_ID, doc_ids=list(document_ids))

    if not KnowledgebaseService.update_by_id(kb.id, {"raptor_task_id": task_id}):
        logging.warning(f"Cannot save raptor_task_id for kb {kb_id}")

    return get_json_result(data={"raptor_task_id": task_id})


@router.get("/trace_raptor")
async def trace_raptor(
    kb_id: str = Query(..., description="知识库ID"),
    current_user = Depends(get_current_user)
):
    if not kb_id:
        return get_error_data_result(message='Lack of "KB ID"')

    ok, kb = KnowledgebaseService.get_by_id(kb_id)
    if not ok:
        return get_error_data_result(message="Invalid Knowledgebase ID")

    task_id = kb.raptor_task_id
    if not task_id:
        return get_json_result(data={})

    ok, task = TaskService.get_by_id(task_id)
    if not ok:
        return get_error_data_result(message="RAPTOR Task Not Found or Error Occurred")

    return get_json_result(data=task.to_dict())


@router.post("/run_mindmap")
async def run_mindmap(
    request: RunMindmapRequest,
    current_user = Depends(get_current_user)
):
    kb_id = request.kb_id
    if not kb_id:
        return get_error_data_result(message='Lack of "KB ID"')

    ok, kb = KnowledgebaseService.get_by_id(kb_id)
    if not ok:
        return get_error_data_result(message="Invalid Knowledgebase ID")

    task_id = kb.mindmap_task_id
    if task_id:
        ok, task = TaskService.get_by_id(task_id)
        if not ok:
            logging.warning(f"A valid Mindmap task id is expected for kb {kb_id}")

        if task and task.progress not in [-1, 1]:
            return get_error_data_result(message=f"Task {task_id} in progress with status {task.progress}. A Mindmap Task is already running.")

    documents, _ = DocumentService.get_by_kb_id(
        kb_id=kb_id,
        page_number=0,
        items_per_page=0,
        orderby="create_time",
        desc=False,
        keywords="",
        run_status=[],
        types=[],
        suffix=[],
    )
    if not documents:
        return get_error_data_result(message=f"No documents in Knowledgebase {kb_id}")

    sample_document = documents[0]
    document_ids = [document["id"] for document in documents]

    task_id = queue_raptor_o_graphrag_tasks(doc=sample_document, ty="mindmap", priority=0, fake_doc_id=GRAPH_RAPTOR_FAKE_DOC_ID, doc_ids=list(document_ids))

    if not KnowledgebaseService.update_by_id(kb.id, {"mindmap_task_id": task_id}):
        logging.warning(f"Cannot save mindmap_task_id for kb {kb_id}")

    return get_json_result(data={"mindmap_task_id": task_id})


@router.get("/trace_mindmap")
async def trace_mindmap(
    kb_id: str = Query(..., description="知识库ID"),
    current_user = Depends(get_current_user)
):
    if not kb_id:
        return get_error_data_result(message='Lack of "KB ID"')

    ok, kb = KnowledgebaseService.get_by_id(kb_id)
    if not ok:
        return get_error_data_result(message="Invalid Knowledgebase ID")

    task_id = kb.mindmap_task_id
    if not task_id:
        return get_json_result(data={})

    ok, task = TaskService.get_by_id(task_id)
    if not ok:
        return get_error_data_result(message="Mindmap Task Not Found or Error Occurred")

    return get_json_result(data=task.to_dict())


@router.delete("/unbind_task")
async def delete_kb_task(
    kb_id: str = Query(..., description="知识库ID"),
    pipeline_task_type: str = Query(..., description="管道任务类型"),
    current_user = Depends(get_current_user)
):
    if not kb_id:
        return get_error_data_result(message='Lack of "KB ID"')
    ok, kb = KnowledgebaseService.get_by_id(kb_id)
    if not ok:
        return get_json_result(data=True)
    if not pipeline_task_type or pipeline_task_type not in [PipelineTaskType.GRAPH_RAG, PipelineTaskType.RAPTOR, PipelineTaskType.MINDMAP]:
        return get_error_data_result(message="Invalid task type")

    match pipeline_task_type:
        case PipelineTaskType.GRAPH_RAG:
            settings.docStoreConn.delete({"knowledge_graph_kwd": ["graph", "subgraph", "entity", "relation"]}, search.index_name(kb.tenant_id), kb_id)
            kb_task_id = "graphrag_task_id"
            kb_task_finish_at = "graphrag_task_finish_at"
        case PipelineTaskType.RAPTOR:
            kb_task_id = "raptor_task_id"
            kb_task_finish_at = "raptor_task_finish_at"
        case PipelineTaskType.MINDMAP:
            kb_task_id = "mindmap_task_id"
            kb_task_finish_at = "mindmap_task_finish_at"
        case _:
            return get_error_data_result(message="Internal Error: Invalid task type")

    ok = KnowledgebaseService.update_by_id(kb_id, {kb_task_id: "", kb_task_finish_at: None})
    if not ok:
        return server_error_response(f"Internal error: cannot delete task {pipeline_task_type}")

    return get_json_result(data=True)
