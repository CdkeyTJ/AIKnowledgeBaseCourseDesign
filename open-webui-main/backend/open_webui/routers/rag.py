from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Annotated, Dict, List, Optional, Any, Tuple
import os
import uuid
import json
from datetime import datetime
import re
from langchain.document_loaders import PyPDFLoader, TextLoader, UnstructuredFileLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import FAISS
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import LLMChainExtractor
from langchain.llms import Ollama

# 项目内部依赖
from open_webui.routers.deps import get_current_active_user
from open_webui.models.users import UserModel
from open_webui.utils import log
from open_webui.config import ERROR_MESSAGES
from open_webui.utils.question_generator import build_prompt, call_qwen_model, parse_model_output
from open_webui.retrieval.vector.dbs.elasticsearch import search as es_search  

# 初始化路由
router = APIRouter(prefix="/api/rag", tags=["RAG Knowledge Base"])

# 配置常量
KB_ROOT_DIR = os.path.join("data", "knowledge_bases")
os.makedirs(KB_ROOT_DIR, exist_ok=True)

# 全局存储（生产环境建议替换为数据库）
user_kbs: Dict[str, Dict[str, Any]] = {}  # {user_id: {kb_id: kb_info}}
vector_stores: Dict[str, Any] = {}  # {user_id_kb_id: FAISS实例}

# 文档处理工具
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    separators=["\n\n", "\n", " ", ""]
)

embeddings = HuggingFaceEmbeddings(
    model_name="all-MiniLM-L6-v2",
    model_kwargs={'device': 'cpu'},
    encode_kwargs={'normalize_embeddings': True}
)

# 数据模型
class KnowledgeBaseCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    collection_name: Optional[str] = None  

class KnowledgeBaseUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class DocumentQuery(BaseModel):
    question: str
    top_k: int = 3

class QuestionGenerateRequest(BaseModel):
    question: str
    difficulty: str = "中等"
    num_questions: int = 1
    question_type: str = "single_choice"  # single_choice, multiple_choice, true_false

# 辅助函数：获取向量存储键
def get_vector_key(user_id: str, kb_id: str) -> str:
    return f"{user_id}_{kb_id}"

# 辅助函数：验证知识库存在
def validate_kb_existence(user_id: str, kb_id: str) -> Dict[str, Any]:
    if user_id not in user_kbs or kb_id not in user_kbs[user_id]:
        raise HTTPException(status_code=404, detail=ERROR_MESSAGES.KB_NOT_FOUND)
    return user_kbs[user_id][kb_id]

# 1. 创建知识库
@router.post("/", response_model=Dict)
async def create_knowledge_base(
    kb_data: KnowledgeBaseCreate,
    current_user: Annotated[UserModel, Depends(get_current_active_user)]
):
    user_id = current_user.id
    kb_id = str(uuid.uuid4())
    kb_dir = os.path.join(KB_ROOT_DIR, user_id, kb_id)
    os.makedirs(kb_dir, exist_ok=True)

    # 初始化用户知识库存储
    if user_id not in user_kbs:
        user_kbs[user_id] = {}

    # 生成默认集合名
    collection_name = kb_data.collection_name or f"kb_{user_id}_{kb_id[:8]}"

    # 存储知识库信息
    kb_info = {
        "id": kb_id,
        "name": kb_data.name,
        "description": kb_data.description,
        "collection_name": collection_name,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "directory": kb_dir,
        "document_count": 0,
        "documents": []  # 存储文档元数据
    }
    user_kbs[user_id][kb_id] = kb_info

    # 初始化向量存储
    vector_key = get_vector_key(user_id, kb_id)
    vector_stores[vector_key] = FAISS.from_texts(["初始化文档"], embeddings)

    # 保存到本地文件（持久化）
    with open(os.path.join(kb_dir, "kb_info.json"), "w", encoding="utf-8") as f:
        json.dump(kb_info, f, ensure_ascii=False, indent=2)

    log.info(f"用户 {user_id} 创建知识库 {kb_id}")
    return {
        "status": "success",
        "data": kb_info
    }

# 2. 获取用户知识库列表
@router.get("/", response_model=Dict)
async def get_user_kbs(
    current_user: Annotated[UserModel, Depends(get_current_active_user)]
):
    user_id = current_user.id
    kbs = user_kbs.get(user_id, {})
    return {
        "status": "success",
        "data": list(kbs.values())
    }

# 3. 上传文档到知识库
@router.post("/{kb_id}/documents", response_model=Dict)
async def upload_document(
    kb_id: str,
    file: UploadFile = File(...),
    current_user: Annotated[UserModel, Depends(get_current_active_user)]
):
    user_id = current_user.id
    kb_info = validate_kb_existence(user_id, kb_id)
    vector_key = get_vector_key(user_id, kb_id)

    # 验证文件类型
    allowed_extensions = {'.pdf', '.txt', '.md', '.docx', '.doc'}
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型，支持: {', '.join(allowed_extensions)}"
        )

    # 保存文件
    file_id = str(uuid.uuid4())
    file_name = f"{file_id}{file_ext}"
    file_path = os.path.join(kb_info["directory"], file_name)

    try:
        # 保存文件内容
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
            file_size = len(content)

        # 加载文档
        if file_ext == '.pdf':
            loader = PyPDFLoader(file_path)
        elif file_ext == '.txt':
            loader = TextLoader(file_path, encoding='utf-8')
        else:
            loader = UnstructuredFileLoader(file_path)  # 处理docx等格式

        documents = loader.load()
        if not documents:
            raise HTTPException(status_code=400, detail="文档内容为空")

        # 文档分割
        split_docs = text_splitter.split_documents(documents)
        if not split_docs:
            raise HTTPException(status_code=400, detail="文档分割失败")

        # 向量化并添加到向量库
        vector_stores[vector_key].add_documents(split_docs)
        
        # 保存向量库
        vector_stores[vector_key].save_local(os.path.join(kb_info["directory"], "vector_db"))

        # 记录文档信息
        doc_info = {
            "id": file_id,
            "filename": file.filename,
            "file_ext": file_ext[1:],
            "file_path": file_path,
            "size": file_size,
            "uploaded_at": datetime.now().isoformat(),
            "chunk_count": len(split_docs)
        }
        kb_info["documents"].append(doc_info)
        kb_info["document_count"] += 1
        kb_info["updated_at"] = datetime.now().isoformat()

        # 更新本地存储
        with open(os.path.join(kb_info["directory"], "kb_info.json"), "w", encoding="utf-8") as f:
            json.dump(kb_info, f, ensure_ascii=False, indent=2)

        log.info(f"用户 {user_id} 向知识库 {kb_id} 上传文档 {file_id}")
        return {
            "status": "success",
            "data": doc_info
        }

    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        log.error(f"文档处理失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"文档处理失败: {str(e)}")
    finally:
        await file.close()

# 4. 从知识库检索相关文档
@router.post("/{kb_id}/retrieve", response_model=Dict)
async def retrieve_documents(
    kb_id: str,
    query: DocumentQuery,
    current_user: Annotated[UserModel, Depends(get_current_active_user)]
):
    user_id = current_user.id
    kb_info = validate_kb_existence(user_id, kb_id)
    vector_key = get_vector_key(user_id, kb_id)

    if vector_key not in vector_stores:
        # 尝试从本地加载向量库
        vector_path = os.path.join(kb_info["directory"], "vector_db")
        if os.path.exists(vector_path):
            vector_stores[vector_key] = FAISS.load_local(
                vector_path, embeddings, allow_dangerous_deserialization=True
            )
        else:
            raise HTTPException(status_code=404, detail="向量库未初始化")

    # 检索相关文档
    try:
        # 基础检索
        docs = vector_stores[vector_key].similarity_search(query.question, k=query.top_k)
        
        # 高级：使用LLM压缩检索结果（可选）
        llm = Ollama(model="qwen2.5:7b", base_url="http://localhost:11434")
        compressor = LLMChainExtractor.from_llm(llm)
        compression_retriever = ContextualCompressionRetriever(
            base_compressor=compressor,
            base_retriever=vector_stores[vector_key].as_retriever(search_kwargs={"k": query.top_k})
        )
        compressed_docs = compression_retriever.get_relevant_documents(query.question)

        # 也可使用项目现有ES检索
        # es_results = es_search(
        #     collection_name=kb_info["collection_name"],
        #     vectors=[embeddings.embed_query(query.question)],
        #     limit=query.top_k
        # )

        return {
            "status": "success",
            "data": {
                "original_docs": [{"content": doc.page_content, "metadata": doc.metadata} for doc in docs],
                "compressed_docs": [{"content": doc.page_content, "metadata": doc.metadata} for doc in compressed_docs],
                "count": len(docs)
            }
        }
    except Exception as e:
        log.error(f"检索失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"检索失败: {str(e)}")

# 5. 基于知识库生成选择题
@router.post("/{kb_id}/generate-questions", response_model=Dict)
async def generate_questions_from_kb(
    kb_id: str,
    request: QuestionGenerateRequest,
    current_user: Annotated[UserModel, Depends(get_current_active_user)]
):
    user_id = current_user.id
    kb_info = validate_kb_existence(user_id, kb_id)

    # 1. 先检索相关文档
    retrieve_response = await retrieve_documents(
        kb_id=kb_id,
        query=DocumentQuery(question=request.question, top_k=5),
        current_user=current_user
    )
    context_docs = retrieve_response["data"]["compressed_docs"]
    context = "\n\n".join([doc["content"] for doc in context_docs])

    if not context.strip():
        raise HTTPException(status_code=400, detail="未检索到相关文档，无法生成题目")

    # 2. 构建生成选择题的Prompt
    prompt_data = {
        "knowledge": context,
        "difficulty": request.difficulty,
        "user_instruction": request.question,
        "single_num": request.num_questions if request.question_type == "single_choice" else 0,
        "multi_num": request.num_questions if request.question_type == "multiple_choice" else 0,
        "truefalse_num": request.num_questions if request.question_type == "true_false" else 0
    }

    try:
        prompt = build_prompt(prompt_data)
        model_response = call_qwen_model(prompt)
        
        # 解析模型输出
        parsed_result = parse_model_output(model_response)
        if not parsed_result:
            raise HTTPException(status_code=500, detail="题目生成失败，解析结果为空")

        return {
            "status": "success",
            "data": {
                "questions": parsed_result,
                "context": context,
                "generated_at": datetime.now().isoformat()
            }
        }
    except Exception as e:
        log.error(f"题目生成失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"题目生成失败: {str(e)}")

# 6. 删除知识库
@router.delete("/{kb_id}", response_model=Dict)
async def delete_knowledge_base(
    kb_id: str,
    current_user: Annotated[UserModel, Depends(get_current_active_user)]
):
    import shutil
    user_id = current_user.id
    kb_info = validate_kb_existence(user_id, kb_id)

    # 删除文件目录
    try:
        if os.path.exists(kb_info["directory"]):
            shutil.rmtree(kb_info["directory"])
        
        # 移除内存存储
        del user_kbs[user_id][kb_id]
        vector_key = get_vector_key(user_id, kb_id)
        if vector_key in vector_stores:
            del vector_stores[vector_key]

        log.info(f"用户 {user_id} 删除知识库 {kb_id}")
        return {"status": "success", "message": "知识库已删除"}
    except Exception as e:
        log.error(f"删除知识库失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"删除知识库失败: {str(e)}")