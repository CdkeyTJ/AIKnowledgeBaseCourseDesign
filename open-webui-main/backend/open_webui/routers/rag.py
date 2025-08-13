from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Dict, Annotated, Optional
import os
import uuid
from datetime import datetime
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.document_loaders import PyPDFLoader, TextLoader
from langchain.vectorstores import FAISS
from langchain.embeddings import HuggingFaceEmbeddings
from open_webui.utils.auth import get_current_active_user
from open_webui.models.user import UserModel

router = APIRouter()

# 全局存储 - 实际生产环境建议使用数据库
user_kbs: Dict[str, Dict[str, Dict]] = {}  # user_id -> kb_id -> kb_info
vector_stores: Dict[str, FAISS] = {}  # vector_key -> FAISS实例

# 初始化文本分割器
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    separators=["\n\n", "\n", "。", "，", " ", ""]
)

# 初始化嵌入模型
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

# 数据模型
class KnowledgeBaseCreate(BaseModel):
    name: str
    description: Optional[str] = ""

class QueryRequest(BaseModel):
    question: str
    top_k: int = 3

# 知识库管理接口
@router.post("/knowledge-bases", response_model=Dict)
async def create_knowledge_base(
    request: Request,
    kb_data: KnowledgeBaseCreate,
    current_user: Annotated[UserModel, Depends(get_current_active_user)]
):
    user_id = current_user.id
    kb_id = str(uuid.uuid4())
    kb_name = kb_data.name
    
    # 创建知识库目录
    base_dir = os.path.join("knowledge_bases", user_id)
    os.makedirs(base_dir, exist_ok=True)
    kb_dir = os.path.join(base_dir, kb_id)
    os.makedirs(kb_dir, exist_ok=True)
    
    # 初始化向量存储
    vector_key = f"{user_id}_{kb_id}"
    vector_stores[vector_key] = FAISS.from_texts([""], embeddings)
    
    # 记录知识库信息
    if user_id not in user_kbs:
        user_kbs[user_id] = {}
    
    user_kbs[user_id][kb_id] = {
        "id": kb_id,
        "name": kb_name,
        "description": kb_data.description,
        "directory": kb_dir,
        "created_at": datetime.now().isoformat(),
        "documents": []
    }
    
    return {
        "status": "success",
        "data": user_kbs[user_id][kb_id]
    }

@router.get("/knowledge-bases", response_model=Dict)
async def get_knowledge_bases(
    current_user: Annotated[UserModel, Depends(get_current_active_user)]
):
    user_id = current_user.id
    return {
        "status": "success",
        "data": list(user_kbs.get(user_id, {}).values())
    }

@router.get("/knowledge-bases/{kb_id}", response_model=Dict)
async def get_knowledge_base(
    kb_id: str,
    current_user: Annotated[UserModel, Depends(get_current_active_user)]
):
    user_id = current_user.id
    if user_id not in user_kbs or kb_id not in user_kbs[user_id]:
        raise HTTPException(status_code=404, detail="知识库不存在")
    
    return {
        "status": "success",
        "data": user_kbs[user_id][kb_id]
    }

# 文档处理接口
@router.post("/knowledge-bases/{kb_id}/documents", response_model=Dict)
async def upload_document(
    kb_id: str,
    file: UploadFile = File(...),
    current_user: Annotated[UserModel, Depends(get_current_active_user)]
):
    user_id = current_user.id
    vector_key = f"{user_id}_{kb_id}"
    
    # 验证知识库存在
    if user_id not in user_kbs or kb_id not in user_kbs[user_id]:
        raise HTTPException(status_code=404, detail="知识库不存在")
    
    kb_info = user_kbs[user_id][kb_id]
    file_ext = os.path.splitext(file.filename)[1].lower()
    
    # 验证文件类型
    if file_ext not in ['.pdf', '.txt']:
        raise HTTPException(status_code=400, detail="仅支持PDF和TXT文件")
    
    # 保存文件
    file_id = str(uuid.uuid4())
    file_path = os.path.join(kb_info["directory"], f"{file_id}{file_ext}")
    
    try:
        # 保存文件内容
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
            file_size = len(content)
        
        # 加载文档
        if file_ext == '.pdf':
            loader = PyPDFLoader(file_path)
            documents = loader.load()
        else:
            loader = TextLoader(file_path, encoding='utf-8')
            documents = loader.load()
        
        # 文档分割
        split_docs = text_splitter.split_documents(documents)
        
        # 向量化并存储
        vector_stores[vector_key].add_documents(split_docs)

        # 记录文档信息
        doc_info = {
            "id": file_id,
            "filename": file.filename,
            "file_type": file_ext[1:],
            "size": file_size,
            "uploaded_at": datetime.now().isoformat(),
            "chunks": len(split_docs)
        }
        kb_info["documents"].append(doc_info)
        
        return {
            "status": "success",
            "data": doc_info
        }
        
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"文档处理失败: {str(e)}")
    finally:
        await file.close()

@router.get("/knowledge-bases/{kb_id}/documents", response_model=Dict)
async def get_documents(
    kb_id: str,
    current_user: Annotated[UserModel, Depends(get_current_active_user)]
):
    user_id = current_user.id
    if user_id not in user_kbs or kb_id not in user_kbs[user_id]:
        raise HTTPException(status_code=404, detail="知识库不存在")
    
    return {
        "status": "success",
        "data": user_kbs[user_id][kb_id]["documents"]
    }

@router.delete("/knowledge-bases/{kb_id}/documents/{doc_id}", response_model=Dict)
async def delete_document(
    kb_id: str,
    doc_id: str,
    current_user: Annotated[UserModel, Depends(get_current_active_user)]
):
    user_id = current_user.id
    if user_id not in user_kbs or kb_id not in user_kbs[user_id]:
        raise HTTPException(status_code=404, detail="知识库不存在")
    
    kb_info = user_kbs[user_id][kb_id]
    doc_index = next((i for i, doc in enumerate(kb_info["documents"]) if doc["id"] == doc_id), None)
    
    if doc_index is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    
    # 删除文件
    doc = kb_info["documents"][doc_index]
    file_path = os.path.join(kb_info["directory"], f"{doc['id']}.{doc['file_type']}")
    if os.path.exists(file_path):
        os.remove(file_path)
    
    # 从列表中移除
    del kb_info["documents"][doc_index]
    
    return {
        "status": "success",
        "message": "文档已删除"
    }

# RAG检索接口
@router.post("/knowledge-bases/{kb_id}/query", response_model=Dict)
async def query_knowledge_base(
    kb_id: str,
    request: QueryRequest,
    current_user: Annotated[UserModel, Depends(get_current_active_user)]
):
    user_id = current_user.id
    vector_key = f"{user_id}_{kb_id}"
    
    if user_id not in user_kbs or kb_id not in user_kbs[user_id]:
        raise HTTPException(status_code=404, detail="知识库不存在")
    
    if vector_key not in vector_stores:
        raise HTTPException(status_code=500, detail="向量存储未初始化")
    
    try:
        # 检索相关文档
        docs = vector_stores[vector_key].similarity_search(
            request.question, 
            k=request.top_k
        )
        
        # 提取内容
        context = "\n\n".join([doc.page_content for doc in docs])
        
        return {
            "status": "success",
            "data": {
                "context": context,
                "sources": [{"page_content": doc.page_content, "metadata": doc.metadata} for doc in docs]
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"检索失败: {str(e)}")

# 供内部调用的检索函数（给question_generator使用）
def retrieve_knowledge(kb_id: str, question: str, top_k: int = 3, user_id: str = None) -> str:
    # 严格 新增用户认证校验
    if not user_id or user_id not in user_kbs or kb_id not in user_kbs[user_id]:
        return ""  # 无权限或知识库不存在时返回空
    
    vector_key = f"{user_id}_{kb_id}"
    if vector_key in vector_stores:
        docs = vector_stores[vector_key].similarity_search(question, k=top_k)
        return "\n\n".join([doc.page_content for doc in docs])
    return ""
