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
import re
import sys
from functools import partial
from typing import Optional

import trio
from fastapi import APIRouter, Depends, Query, Header, UploadFile, File, Form
from fastapi.responses import StreamingResponse, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from agent.component import LLM
from api import settings
from api.db import CanvasCategory, FileType
from api.db.services.canvas_service import CanvasTemplateService, UserCanvasService, API4ConversationService
from api.db.services.document_service import DocumentService
from api.db.services.file_service import FileService
from api.db.services.pipeline_operation_log_service import PipelineOperationLogService
from api.db.services.task_service import queue_dataflow, CANVAS_DEBUG_DOC_ID, TaskService
from api.db.services.user_service import TenantService
from api.db.services.user_canvas_version import UserCanvasVersionService
from api.settings import RetCode
from api.utils import get_uuid
from api.utils.api_utils import get_json_result, server_error_response, get_data_error_result
from api.apps.models.auth_dependencies import get_current_user
from api.apps.models.canvas_models import (
    DeleteCanvasRequest,
    SaveCanvasRequest,
    CompletionRequest,
    RerunRequest,
    ResetCanvasRequest,
    InputFormQuery,
    DebugRequest,
    TestDBConnectRequest,
    ListCanvasQuery,
    SettingRequest,
    TraceQuery,
    ListSessionsQuery,
    DownloadQuery,
    UploadQuery,
)
from agent.canvas import Canvas
from peewee import MySQLDatabase, PostgresqlDatabase
from api.db.db_models import APIToken, Task
import time

from api.utils.file_utils import filename_type, read_potential_broken_pdf
from rag.flow.pipeline import Pipeline
from rag.nlp import search
from rag.utils.redis_conn import REDIS_CONN

# 创建路由器
router = APIRouter()


@router.get('/templates')
async def templates(
    current_user = Depends(get_current_user)
):
    """获取画布模板列表"""
    return get_json_result(data=[c.to_dict() for c in CanvasTemplateService.get_all()])


@router.post('/rm')
async def rm(
    request: DeleteCanvasRequest,
    current_user = Depends(get_current_user)
):
    """删除画布"""
    for i in request.canvas_ids:
        if not UserCanvasService.accessible(i, current_user.id):
            return get_json_result(
                data=False, message='Only owner of canvas authorized for this operation.',
                code=RetCode.OPERATING_ERROR)
        UserCanvasService.delete_by_id(i)
    return get_json_result(data=True)


@router.post('/set')
async def save(
    request: SaveCanvasRequest,
    current_user = Depends(get_current_user)
):
    """保存画布"""
    req = request.model_dump(exclude_unset=True)
    if not isinstance(req["dsl"], str):
        req["dsl"] = json.dumps(req["dsl"], ensure_ascii=False)
    req["dsl"] = json.loads(req["dsl"])
    cate = req.get("canvas_category", CanvasCategory.Agent)
    if "id" not in req or not req.get("id"):
        req["user_id"] = current_user.id
        if UserCanvasService.query(user_id=current_user.id, title=req["title"].strip(), canvas_category=cate):
            return get_data_error_result(message=f"{req['title'].strip()} already exists.")
        req["id"] = get_uuid()
        if not UserCanvasService.save(**req):
            return get_data_error_result(message="Fail to save canvas.")
    else:
        if not UserCanvasService.accessible(req["id"], current_user.id):
            return get_json_result(
                data=False, message='Only owner of canvas authorized for this operation.',
                code=RetCode.OPERATING_ERROR)
        UserCanvasService.update_by_id(req["id"], req)
    # save version
    UserCanvasVersionService.insert(user_canvas_id=req["id"], dsl=req["dsl"], title="{0}_{1}".format(req["title"], time.strftime("%Y_%m_%d_%H_%M_%S")))
    UserCanvasVersionService.delete_all_versions(req["id"])
    return get_json_result(data=req)


@router.get('/get/{canvas_id}')
async def get(
    canvas_id: str,
    current_user = Depends(get_current_user)
):
    """获取画布详情"""
    if not UserCanvasService.accessible(canvas_id, current_user.id):
        return get_data_error_result(message="canvas not found.")
    e, c = UserCanvasService.get_by_canvas_id(canvas_id)
    return get_json_result(data=c)


@router.get('/getsse/{canvas_id}')
async def getsse(
    canvas_id: str,
    authorization: str = Header(..., description="Authorization header")
):
    """获取画布详情（SSE，通过API token认证）"""
    token_parts = authorization.split()
    if len(token_parts) != 2:
        return get_data_error_result(message='Authorization is not valid!"')
    token = token_parts[1]
    objs = APIToken.query(beta=token)
    if not objs:
        return get_data_error_result(message='Authentication error: API key is invalid!"')
    tenant_id = objs[0].tenant_id
    if not UserCanvasService.query(user_id=tenant_id, id=canvas_id):
        return get_json_result(
            data=False,
            message='Only owner of canvas authorized for this operation.',
            code=RetCode.OPERATING_ERROR
        )
    e, c = UserCanvasService.get_by_id(canvas_id)
    if not e or c.user_id != tenant_id:
        return get_data_error_result(message="canvas not found.")
    return get_json_result(data=c.to_dict())


@router.post('/completion')
async def run(
    request: CompletionRequest,
    current_user = Depends(get_current_user)
):
    """运行画布（完成/执行）"""
    query = request.query or ""
    files = request.files or []
    inputs = request.inputs or {}
    user_id = request.user_id or current_user.id
    
    if not UserCanvasService.accessible(request.id, current_user.id):
        return get_json_result(
            data=False, message='Only owner of canvas authorized for this operation.',
            code=RetCode.OPERATING_ERROR)

    e, cvs = UserCanvasService.get_by_id(request.id)
    if not e:
        return get_data_error_result(message="canvas not found.")

    if not isinstance(cvs.dsl, str):
        cvs.dsl = json.dumps(cvs.dsl, ensure_ascii=False)

    if cvs.canvas_category == CanvasCategory.DataFlow:
        task_id = get_uuid()
        Pipeline(cvs.dsl, tenant_id=current_user.id, doc_id=CANVAS_DEBUG_DOC_ID, task_id=task_id, flow_id=request.id)
        ok, error_message = queue_dataflow(tenant_id=user_id, flow_id=request.id, task_id=task_id, file=files[0] if files else None, priority=0)
        if not ok:
            return get_data_error_result(message=error_message)
        return get_json_result(data={"message_id": task_id})

    try:
        canvas = Canvas(cvs.dsl, current_user.id, request.id)
    except Exception as e:
        return server_error_response(e)

    async def sse():
        nonlocal canvas, user_id
        try:
            for ans in canvas.run(query=query, files=files, user_id=user_id, inputs=inputs):
                yield "data:" + json.dumps(ans, ensure_ascii=False) + "\n\n"

            cvs.dsl = json.loads(str(canvas))
            UserCanvasService.update_by_id(request.id, cvs.to_dict())
        except Exception as e:
            logging.exception(e)
            yield "data:" + json.dumps({"code": 500, "message": str(e), "data": False}, ensure_ascii=False) + "\n\n"

    return StreamingResponse(
        sse(),
        media_type="text/event-stream",
        headers={
            "Cache-control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Type": "text/event-stream; charset=utf-8"
        }
    )


@router.post('/rerun')
async def rerun(
    request: RerunRequest,
    current_user = Depends(get_current_user)
):
    """重新运行流水线"""
    doc = PipelineOperationLogService.get_documents_info(request.id)
    if not doc:
        return get_data_error_result(message="Document not found.")
    doc = doc[0]
    if 0 < doc["progress"] < 1:
        return get_data_error_result(message=f"`{doc['name']}` is processing...")

    if settings.docStoreConn.indexExist(search.index_name(current_user.id), doc["kb_id"]):
        settings.docStoreConn.delete({"doc_id": doc["id"]}, search.index_name(current_user.id), doc["kb_id"])
    doc["progress_msg"] = ""
    doc["chunk_num"] = 0
    doc["token_num"] = 0
    DocumentService.clear_chunk_num_when_rerun(doc["id"])
    DocumentService.update_by_id(request.id, doc)
    TaskService.filter_delete([Task.doc_id == request.id])

    dsl = request.dsl
    dsl["path"] = [request.component_id]
    PipelineOperationLogService.update_by_id(request.id, {"dsl": dsl})
    queue_dataflow(tenant_id=current_user.id, flow_id=request.id, task_id=get_uuid(), doc_id=doc["id"], priority=0, rerun=True)
    return get_json_result(data=True)


@router.put('/cancel/{task_id}')
async def cancel(
    task_id: str,
    current_user = Depends(get_current_user)
):
    """取消任务"""
    try:
        REDIS_CONN.set(f"{task_id}-cancel", "x")
    except Exception as e:
        logging.exception(e)
    return get_json_result(data=True)


@router.post('/reset')
async def reset(
    request: ResetCanvasRequest,
    current_user = Depends(get_current_user)
):
    """重置画布"""
    if not UserCanvasService.accessible(request.id, current_user.id):
        return get_json_result(
            data=False, message='Only owner of canvas authorized for this operation.',
            code=RetCode.OPERATING_ERROR)
    try:
        e, user_canvas = UserCanvasService.get_by_id(request.id)
        if not e:
            return get_data_error_result(message="canvas not found.")

        canvas = Canvas(json.dumps(user_canvas.dsl), current_user.id)
        canvas.reset()
        dsl = json.loads(str(canvas))
        UserCanvasService.update_by_id(request.id, {"dsl": dsl})
        return get_json_result(data=dsl)
    except Exception as e:
        return server_error_response(e)


@router.post("/upload/{canvas_id}")
async def upload(
    canvas_id: str,
    url: Optional[str] = Query(None, description="URL（可选，用于从URL下载）"),
    file: Optional[UploadFile] = File(None, description="上传的文件")
):
    """上传文件到画布"""
    e, cvs = UserCanvasService.get_by_canvas_id(canvas_id)
    if not e:
        return get_data_error_result(message="canvas not found.")

    user_id = cvs["user_id"]
    
    def structured(filename, filetype, blob, content_type):
        nonlocal user_id
        if filetype == FileType.PDF.value:
            blob = read_potential_broken_pdf(blob)

        location = get_uuid()
        FileService.put_blob(user_id, location, blob)

        return {
            "id": location,
            "name": filename,
            "size": sys.getsizeof(blob),
            "extension": filename.split(".")[-1].lower(),
            "mime_type": content_type,
            "created_by": user_id,
            "created_at": time.time(),
            "preview_url": None
        }

    if url:
        from crawl4ai import (
            AsyncWebCrawler,
            BrowserConfig,
            CrawlerRunConfig,
            DefaultMarkdownGenerator,
            PruningContentFilter,
            CrawlResult
        )
        try:
            filename = re.sub(r"\?.*", "", url.split("/")[-1])
            async def adownload():
                browser_config = BrowserConfig(
                    headless=True,
                    verbose=False,
                )
                async with AsyncWebCrawler(config=browser_config) as crawler:
                    crawler_config = CrawlerRunConfig(
                        markdown_generator=DefaultMarkdownGenerator(
                            content_filter=PruningContentFilter()
                        ),
                        pdf=True,
                        screenshot=False
                    )
                    result: CrawlResult = await crawler.arun(
                        url=url,
                        config=crawler_config
                    )
                    return result
            page = trio.run(adownload())
            if page.pdf:
                if filename.split(".")[-1].lower() != "pdf":
                    filename += ".pdf"
                return get_json_result(data=structured(filename, "pdf", page.pdf, page.response_headers.get("content-type", "application/pdf")))

            return get_json_result(data=structured(filename, "html", str(page.markdown).encode("utf-8"), page.response_headers.get("content-type", "text/html"), user_id))

        except Exception as e:
            return server_error_response(e)

    if not file:
        return get_data_error_result(message="No file provided.")
    
    try:
        DocumentService.check_doc_health(user_id, file.filename)
        blob = await file.read()
        return get_json_result(data=structured(file.filename, filename_type(file.filename), blob, file.content_type or "application/octet-stream"))
    except Exception as e:
        return server_error_response(e)


@router.get('/input_form')
async def input_form(
    id: str = Query(..., description="画布ID"),
    component_id: str = Query(..., description="组件ID"),
    current_user = Depends(get_current_user)
):
    """获取组件输入表单"""
    try:
        e, user_canvas = UserCanvasService.get_by_id(id)
        if not e:
            return get_data_error_result(message="canvas not found.")
        if not UserCanvasService.query(user_id=current_user.id, id=id):
            return get_json_result(
                data=False, message='Only owner of canvas authorized for this operation.',
                code=RetCode.OPERATING_ERROR)

        canvas = Canvas(json.dumps(user_canvas.dsl), current_user.id)
        return get_json_result(data=canvas.get_component_input_form(component_id))
    except Exception as e:
        return server_error_response(e)


@router.post('/debug')
async def debug(
    request: DebugRequest,
    current_user = Depends(get_current_user)
):
    """调试组件"""
    if not UserCanvasService.accessible(request.id, current_user.id):
        return get_json_result(
            data=False, message='Only owner of canvas authorized for this operation.',
            code=RetCode.OPERATING_ERROR)
    try:
        e, user_canvas = UserCanvasService.get_by_id(request.id)
        canvas = Canvas(json.dumps(user_canvas.dsl), current_user.id)
        canvas.reset()
        canvas.message_id = get_uuid()
        component = canvas.get_component(request.component_id)["obj"]
        component.reset()

        if isinstance(component, LLM):
            component.set_debug_inputs(request.params)
        component.invoke(**{k: o["value"] for k,o in request.params.items()})
        outputs = component.output()
        for k in outputs.keys():
            if isinstance(outputs[k], partial):
                txt = ""
                for c in outputs[k]():
                    txt += c
                outputs[k] = txt
        return get_json_result(data=outputs)
    except Exception as e:
        return server_error_response(e)


@router.post('/test_db_connect')
async def test_db_connect(
    request: TestDBConnectRequest,
    current_user = Depends(get_current_user)
):
    """测试数据库连接"""
    req = request.model_dump()
    try:
        if req["db_type"] in ["mysql", "mariadb"]:
            db = MySQLDatabase(req["database"], user=req["username"], host=req["host"], port=req["port"],
                               password=req["password"])
        elif req["db_type"] == 'postgres':
            db = PostgresqlDatabase(req["database"], user=req["username"], host=req["host"], port=req["port"],
                                    password=req["password"])
        elif req["db_type"] == 'mssql':
            import pyodbc
            connection_string = (
                f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                f"SERVER={req['host']},{req['port']};"
                f"DATABASE={req['database']};"
                f"UID={req['username']};"
                f"PWD={req['password']};"
            )
            db = pyodbc.connect(connection_string)
            cursor = db.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
        elif req["db_type"] == 'IBM DB2':
            import ibm_db
            conn_str = (
                f"DATABASE={req['database']};"
                f"HOSTNAME={req['host']};"
                f"PORT={req['port']};"
                f"PROTOCOL=TCPIP;"
                f"UID={req['username']};"
                f"PWD={req['password']};"
            )
            logging.info(conn_str)
            conn = ibm_db.connect(conn_str, "", "")
            stmt = ibm_db.exec_immediate(conn, "SELECT 1 FROM sysibm.sysdummy1")
            ibm_db.fetch_assoc(stmt)
            ibm_db.close(conn)
            return get_json_result(data="Database Connection Successful!")
        elif req["db_type"] == 'trino':
            def _parse_catalog_schema(db: str):
                if not db:
                    return None, None
                if "." in db:
                    c, s = db.split(".", 1)
                elif "/" in db:
                    c, s = db.split("/", 1)
                else:
                    c, s = db, "default"
                return c, s
            try:
                import trino
                import os
                from trino.auth import BasicAuthentication
            except Exception:
                return server_error_response("Missing dependency 'trino'. Please install: pip install trino")

            catalog, schema = _parse_catalog_schema(req["database"])
            if not catalog:
                return server_error_response("For Trino, 'database' must be 'catalog.schema' or at least 'catalog'.")
            
            http_scheme = "https" if os.environ.get("TRINO_USE_TLS", "0") == "1" else "http"

            auth = None
            if http_scheme == "https" and req.get("password"):
                auth = BasicAuthentication(req.get("username") or "ragflow", req["password"])

            conn = trino.dbapi.connect(
                host=req["host"],
                port=int(req["port"] or 8080),
                user=req["username"] or "ragflow",
                catalog=catalog,
                schema=schema or "default",
                http_scheme=http_scheme,
                auth=auth
            )
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchall()
            cur.close()
            conn.close()
            return get_json_result(data="Database Connection Successful!")
        else:
            return server_error_response("Unsupported database type.")
        if req["db_type"] != 'mssql':
            db.connect()
        db.close()

        return get_json_result(data="Database Connection Successful!")
    except Exception as e:
        return server_error_response(e)


#api get list version dsl of canvas
@router.get('/getlistversion/{canvas_id}')
async def getlistversion(
    canvas_id: str,
    current_user = Depends(get_current_user)
):
    """获取画布版本列表"""
    try:
        list = sorted([c.to_dict() for c in UserCanvasVersionService.list_by_canvas_id(canvas_id)], key=lambda x: x["update_time"]*-1)
        return get_json_result(data=list)
    except Exception as e:
        return get_data_error_result(message=f"Error getting history files: {e}")


@router.get('/getversion/{version_id}')
async def getversion(
    version_id: str,
    current_user = Depends(get_current_user)
):
    """获取画布版本详情"""
    try:
        e, version = UserCanvasVersionService.get_by_id(version_id)
        if version:
            return get_json_result(data=version.to_dict())
        return get_data_error_result(message="Version not found.")
    except Exception as e:
        return get_data_error_result(message=f"Error getting history file: {e}")


@router.get('/list')
async def list_canvas(
    query: ListCanvasQuery = Depends(),
    current_user = Depends(get_current_user)
):
    """列出画布"""
    keywords = query.keywords or ""
    page_number = int(query.page or 0)
    items_per_page = int(query.page_size or 0)
    orderby = query.orderby or "create_time"
    canvas_category = query.canvas_category
    desc = query.desc.lower() == "false" if query.desc else True
    owner_ids = [id for id in (query.owner_ids or "").strip().split(",") if id]
    
    if not owner_ids:
        tenants = TenantService.get_joined_tenants_by_user_id(current_user.id)
        tenants = [m["tenant_id"] for m in tenants]
        tenants.append(current_user.id)
        canvas, total = UserCanvasService.get_by_tenant_ids(
            tenants, current_user.id, page_number,
            items_per_page, orderby, desc, keywords, canvas_category)
    else:
        tenants = owner_ids
        canvas, total = UserCanvasService.get_by_tenant_ids(
            tenants, current_user.id, 0,
            0, orderby, desc, keywords, canvas_category)
    return get_json_result(data={"canvas": canvas, "total": total})


@router.post('/setting')
async def setting(
    request: SettingRequest,
    current_user = Depends(get_current_user)
):
    """设置画布"""
    if not UserCanvasService.accessible(request.id, current_user.id):
        return get_json_result(
            data=False, message='Only owner of canvas authorized for this operation.',
            code=RetCode.OPERATING_ERROR)

    e, flow = UserCanvasService.get_by_id(request.id)
    if not e:
        return get_data_error_result(message="canvas not found.")
    flow = flow.to_dict()
    flow["title"] = request.title

    for key in ["description", "permission", "avatar"]:
        value = getattr(request, key, None)
        if value:
            flow[key] = value

    num = UserCanvasService.update_by_id(request.id, flow)
    return get_json_result(data=num)


@router.get('/trace')
async def trace(
    canvas_id: str = Query(..., description="画布ID"),
    message_id: str = Query(..., description="消息ID")
):
    """追踪日志"""
    try:
        bin = REDIS_CONN.get(f"{canvas_id}-{message_id}-logs")
        if not bin:
            return get_json_result(data={})

        return get_json_result(data=json.loads(bin.encode("utf-8")))
    except Exception as e:
        logging.exception(e)
        return server_error_response(e)


@router.get('/{canvas_id}/sessions')
async def sessions(
    canvas_id: str,
    query: ListSessionsQuery = Depends(),
    current_user = Depends(get_current_user)
):
    """列出画布会话"""
    tenant_id = current_user.id
    if not UserCanvasService.accessible(canvas_id, tenant_id):
        return get_json_result(
            data=False, message='Only owner of canvas authorized for this operation.',
            code=RetCode.OPERATING_ERROR)

    user_id = query.user_id
    page_number = int(query.page or 1)
    items_per_page = int(query.page_size or 30)
    keywords = query.keywords
    from_date = query.from_date
    to_date = query.to_date
    orderby = query.orderby or "update_time"
    desc = query.desc.lower() in ["false", "False"] if query.desc else True
    # dsl defaults to True in all cases except for False and false
    include_dsl = query.dsl.lower() not in ["false", "False"] if query.dsl else True
    
    total, sess = API4ConversationService.get_list(canvas_id, tenant_id, page_number, items_per_page, orderby, desc,
                                             None, user_id, include_dsl, keywords, from_date, to_date)
    try:
        return get_json_result(data={"total": total, "sessions": sess})
    except Exception as e:
        return server_error_response(e)


@router.get('/prompts')
async def prompts(
    current_user = Depends(get_current_user)
):
    """获取提示词模板"""
    from rag.prompts.generator import ANALYZE_TASK_SYSTEM, ANALYZE_TASK_USER, NEXT_STEP, REFLECT, CITATION_PROMPT_TEMPLATE
    return get_json_result(data={
        "task_analysis": ANALYZE_TASK_SYSTEM +"\n\n"+ ANALYZE_TASK_USER,
        "plan_generation": NEXT_STEP,
        "reflection": REFLECT,
        #"context_summary": SUMMARY4MEMORY,
        #"context_ranking": RANK_MEMORY,
        "citation_guidelines": CITATION_PROMPT_TEMPLATE
    })


@router.get('/download')
async def download(
    id: str = Query(..., description="文件ID"),
    created_by: str = Query(..., description="创建者ID")
):
    """下载文件"""
    blob = FileService.get_blob(created_by, id)
    return Response(content=blob)