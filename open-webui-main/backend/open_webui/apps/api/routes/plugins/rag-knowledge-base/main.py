from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Dict, Optional, Annotated
import os
import shutil
import uuid
import json
from datetime import datetime

from backend.apps.api.deps import get_current_active_user
from backend.apps.web.models.users import UserModel
from backend.settings import settings

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA
from langchain_community.llms import OpenAI  # 可替换为其他LLM
from langchain.prompts import PromptTemplate
from langchain_community.callbacks.manager import get_openai_callback

# 初始化路由
router = APIRouter(prefix="/plugins/rag-knowledge-base", tags=["RAG Knowledge Base"])

# 配置存储路径
KB_ROOT_DIR = os.path.join(settings.DATA_DIR, "rag_knowledge_bases")
os.makedirs(KB_ROOT_DIR, exist_ok=True)

# 数据模型
class KnowledgeBaseCreate(BaseModel):
    name: str
    description: Optional[str] = ""

class QuestionRequest(BaseModel):
    question: str

class MultipleChoiceRequest(BaseModel):
    num_questions: int = 3
    difficulty: str = "medium"  # easy, medium, hard

# 全局存储 - 生产环境可替换为数据库
user_kbs: Dict[str, Dict[str, Dict]] = {}  # {user_id: {kb_id: {details}}}
vector_stores: Dict[str, FAISS] = {}       # {user_id_kb_id: FAISS实例}

# 初始化嵌入模型
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

# 文本分割器
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    separators=["\n\n", "\n", ".", " ", ""]
)

# 创建知识库
@router.post("/", response_model=Dict)
async def create_knowledge_base(
    kb_data: KnowledgeBaseCreate,
    current_user: Annotated[UserModel, Depends(get_current_active_user)]
):
    user_id = current_user.id
    kb_id = str(uuid.uuid4())
    kb_dir = os.path.join(KB_ROOT_DIR, user_id, kb_id)
    os.makedirs(kb_dir, exist_ok=True)
    
    if user_id not in user_kbs:
        user_kbs[user_id] = {}
    
    user_kbs[user_id][kb_id] = {
        "id": kb_id,
        "name": kb_data.name,
        "description": kb_data.description,
        "created_at": datetime.now().isoformat(),
        "directory": kb_dir,
        "documents": []
    }
    
    # 初始化向量存储
    vector_key = f"{user_id}_{kb_id}"
    vector_stores[vector_key] = FAISS.from_texts([""], embeddings)
    
    return {
        "status": "success",
        "data": {
            "id": kb_id,
            "name": kb_data.name,
            "description": kb_data.description
        }
    }

# 获取用户所有知识库
@router.get("/", response_model=Dict)
async def get_user_knowledge_bases(
    current_user: Annotated[UserModel, Depends(get_current_active_user)]
):
    user_id = current_user.id
    kbs = user_kbs.get(user_id, {})
    
    result = []
    for kb_id, kb_info in kbs.items():
        result.append({
            "id": kb_id,
            "name": kb_info["name"],
            "description": kb_info["description"],
            "created_at": kb_info["created_at"],
            "document_count": len(kb_info["documents"])
        })
    
    return {
        "status": "success",
        "data": result
    }

# 上传文档到知识库（带RAG预处理）
@router.post("/{kb_id}/documents", response_model=Dict)
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
        
        # 文档分割（RAG关键步骤1）
        split_docs = text_splitter.split_documents(documents)
        
        # 向量化并存储（RAG关键步骤2）
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

# 基于知识库的问答（RAG核心功能）
@router.post("/{kb_id}/query", response_model=Dict)
async def query_knowledge_base(
    kb_id: str,
    request: QuestionRequest,
    current_user: Annotated[UserModel, Depends(get_current_active_user)]
):
    user_id = current_user.id
    vector_key = f"{user_id}_{kb_id}"
    
    # 验证知识库
    if vector_key not in vector_stores:
        raise HTTPException(status_code=404, detail="知识库不存在或未初始化")
    
    # 创建检索器（RAG关键步骤3）
    retriever = vector_stores[vector_key].as_retriever(
        search_kwargs={"k": 4}  # 检索最相关的4个片段
    )
    
    # 自定义提示模板
    prompt_template = """使用以下提供的上下文来回答问题。如果上下文里没有相关信息，直接说"根据提供的知识库，我无法回答这个问题"。

    上下文:
    {context}

    问题: {question}
    回答:"""
    
    PROMPT = PromptTemplate(
        template=prompt_template,
        input_variables=["context", "question"]
    )
    
    # 创建QA链（RAG关键步骤4）
    qa_chain = RetrievalQA.from_chain_type(
        llm=OpenAI(temperature=0),  # 可替换为本地模型
        chain_type="stuff",
        retriever=retriever,
        return_source_documents=True,
        chain_type_kwargs={"prompt": PROMPT}
    )
    
    # 执行问答
    with get_openai_callback() as cb:
        result = qa_chain({"query": request.question})
        
        return {
            "status": "success",
            "data": {
                "question": request.question,
                "answer": result["result"],
                "sources": [
                    {
                        "content": doc.page_content[:150] + "...",
                        "metadata": doc.metadata
                    } for doc in result["source_documents"]
                ],
                "token_usage": cb.total_tokens
            }
        }

# 从知识库生成选择题
@router.post("/{kb_id}/generate-questions", response_model=Dict)
async def generate_questions(
    kb_id: str,
    request: MultipleChoiceRequest,
    current_user: Annotated[UserModel, Depends(get_current_active_user)]
):
    user_id = current_user.id
    vector_key = f"{user_id}_{kb_id}"
    
    if vector_key not in vector_stores:
        raise HTTPException(status_code=404, detail="知识库不存在")
    
    # 检索相关文档片段
    sample_docs = vector_stores[vector_key].similarity_search("", k=request.num_questions * 2)
    context = "\n\n".join([doc.page_content for doc in sample_docs])
    
    # 生成题目提示
    prompt = PromptTemplate(
        input_variables=["context", "num_questions", "difficulty"],
        template="""基于以下内容，生成{num_questions}道{difficulty}难度的选择题。
        要求：
        1. 每道题有4个选项（A、B、C、D），只有一个正确答案
        2. 错误选项应具有迷惑性，但明显不正确
        3. 所有问题和选项必须基于提供的内容，不得编造
        
        输出格式为JSON数组：
        [
            {
                "question": "问题内容",
                "options": ["A选项", "B选项", "C选项", "D选项"],
                "correct_answer": "A"
            },
            ...
        ]
        
        内容:
        {context}
        """
    )
    
    # 调用LLM生成题目
    llm = OpenAI(temperature=0.7)
    with get_openai_callback() as cb:
        response = llm(prompt.format(
            context=context,
            num_questions=request.num_questions,
            difficulty=request.difficulty
        ))
        
        try:
            # 提取并解析JSON
            json_start = response.find('[')
            json_end = response.rfind(']') + 1
            questions = json.loads(response[json_start:json_end])
            
            return {
                "status": "success",
                "data": {
                    "questions": questions,
                    "token_usage": cb.total_tokens
                }
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"题目生成失败: {str(e)}")

# 其他辅助接口（文档列表、删除等）
@router.get("/{kb_id}/documents", response_model=Dict)
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

@router.delete("/{kb_id}/documents/{doc_id}", response_model=Dict)
async def delete_document(
    kb_id: str,
    doc_id: str,
    current_user: Annotated[UserModel, Depends(get_current_active_user)]
):
    user_id = current_user.id
    if user_id not in user_kbs or kb_id not in user_kbs[user_id]:
        raise HTTPException(status_code=404, detail="知识库不存在")
    
    kb_info = user_kbs[user_id][kb_id]
    vector_key = f"{user_id}_{kb_id}"
    
    # 查找并删除文档
    for i, doc in enumerate(kb_info["documents"]):
        if doc["id"] == doc_id:
            # 删除文件
            if os.path.exists(doc["file_path"]):
                os.remove(doc["file_path"])
            
            # 从列表移除
            del kb_info["documents"][i]
            
            # 重建向量库
            all_docs = []
            for remaining_doc in kb_info["documents"]:
                if remaining_doc["file_type"] == 'pdf':
                    loader = PyPDFLoader(remaining_doc["file_path"])
                    docs = loader.load()
                else:
                    loader = TextLoader(remaining_doc["file_path"])
                    docs = loader.load()
                all_docs.extend(text_splitter.split_documents(docs))
            
            vector_stores[vector_key] = FAISS.from_documents(all_docs, embeddings)
            return {"status": "success", "message": "文档已删除"}
    
    raise HTTPException(status_code=404, detail="文档不存在")

@router.delete("/{kb_id}", response_model=Dict)
async def delete_knowledge_base(
    kb_id: str,
    current_user: Annotated[UserModel, Depends(get_current_active_user)]
):
    user_id = current_user.id
    if user_id not in user_kbs or kb_id not in user_kbs[user_id]:
        raise HTTPException(status_code=404, detail="知识库不存在")
    
    # 删除文件和目录
    kb_dir = user_kbs[user_id][kb_id]["directory"]
    if os.path.exists(kb_dir):
        shutil.rmtree(kb_dir)
    
    # 清理内存数据
    del user_kbs[user_id][kb_id]
    vector_key = f"{user_id}_{kb_id}"
    if vector_key in vector_stores:
        del vector_stores[vector_key]
    
    return {"status": "success", "message": "知识库已删除"}
    