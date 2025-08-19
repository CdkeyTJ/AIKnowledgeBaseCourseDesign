from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Dict, Annotated, Optional
import os
import uuid
import json
import pickle
from datetime import datetime
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.document_loaders import PyPDFLoader, TextLoader
from langchain.vectorstores import FAISS
from langchain.embeddings import HuggingFaceEmbeddings
from open_webui.utils.auth import get_current_user
from open_webui.models.users import UserModel

router = APIRouter()

# 持久化存储路径
STORAGE_DIR = "rag_storage"
METADATA_FILE = "metadata.json"
VECTOR_DIR = "vectors"

# 确保存储目录存在
os.makedirs(STORAGE_DIR, exist_ok=True)
os.makedirs(os.path.join(STORAGE_DIR, VECTOR_DIR), exist_ok=True)

# 全局存储 - 实际生产环境建议使用数据库
user_kbs: Dict[str, Dict[str, Dict]] = {}  # user_id -> kb_id -> kb_info
vector_stores: Dict[str, FAISS] = {}  # vector_key -> FAISS实例

# 初始化文本分割器
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,  # 减小分块大小，提高检索精度
    chunk_overlap=100,  # 减小重叠，避免重复
    separators=["\n\n", "\n", "。", "，", " ", ""]
)

# 初始化嵌入模型
embeddings = HuggingFaceEmbeddings(
    model_name="all-MiniLM-L6-v2",
    model_kwargs={'device': 'cpu'},  # 确保设备一致性
    encode_kwargs={'normalize_embeddings': True}  # 标准化嵌入向量
)

# 数据模型
class KnowledgeBaseCreate(BaseModel):
    name: str
    description: Optional[str] = ""

class QueryRequest(BaseModel):
    question: str
    top_k: int = 3

# 持久化存储函数
def save_metadata():
    """保存知识库元数据到文件"""
    metadata_path = os.path.join(STORAGE_DIR, METADATA_FILE)
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(user_kbs, f, ensure_ascii=False, indent=2, default=str)

def load_metadata():
    """从文件加载知识库元数据"""
    metadata_path = os.path.join(STORAGE_DIR, METADATA_FILE)
    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 转换时间字符串为datetime对象
                for user_id, kbs in data.items():
                    for kb_id, kb_info in kbs.items():
                        if 'created_at' in kb_info:
                            kb_info['created_at'] = datetime.fromisoformat(kb_info['created_at'])
                return data
        except Exception as e:
            print(f"加载元数据失败: {e}")
    return {}

def save_vector_store(vector_key: str, vector_store: FAISS):
    """保存向量存储到文件"""
    vector_path = os.path.join(STORAGE_DIR, VECTOR_DIR, f"{vector_key}.pkl")
    try:
        with open(vector_path, 'wb') as f:
            pickle.dump(vector_store, f)
    except Exception as e:
        print(f"保存向量存储失败: {e}")

def load_vector_store(vector_key: str) -> Optional[FAISS]:
    """从文件加载向量存储"""
    vector_path = os.path.join(STORAGE_DIR, VECTOR_DIR, f"{vector_key}.pkl")
    if os.path.exists(vector_path):
        try:
            with open(vector_path, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            print(f"加载向量存储失败: {e}")
    return None

# 启动时加载数据
def initialize_storage():
    """初始化存储，加载已保存的数据"""
    global user_kbs, vector_stores
    
    # 加载元数据
    user_kbs = load_metadata()
    
    # 加载向量存储
    for user_id, kbs in user_kbs.items():
        for kb_id in kbs.keys():
            vector_key = f"{user_id}_{kb_id}"
            vector_store = load_vector_store(vector_key)
            if vector_store:
                vector_stores[vector_key] = vector_store
                print(f"已加载向量存储: {vector_key}")
            else:
                # 如果没有保存的向量存储，设置为None（等待文档上传）
                vector_stores[vector_key] = None
                print(f"向量存储为空: {vector_key}，等待文档上传")

# 在模块加载时初始化
initialize_storage()

# 知识库管理接口
@router.post("/knowledge-bases", response_model=Dict)
async def create_knowledge_base(
    request: Request,
    kb_data: KnowledgeBaseCreate,
    current_user: Annotated[UserModel, Depends(get_current_user)]
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
    # 不要用空字符串初始化，这会导致问题
    # vector_stores[vector_key] = FAISS.from_texts([""], embeddings)
    # 创建空的向量存储，等待文档上传
    vector_stores[vector_key] = None
    
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
    
    # @CDK: 保存元数据到文件
    save_metadata()
    
    return {
        "status": "success",
        "data": user_kbs[user_id][kb_id]
    }

@router.get("/knowledge-bases", response_model=Dict)
async def get_knowledge_bases(
    current_user: Annotated[UserModel, Depends(get_current_user)]
):
    user_id = current_user.id
    return {
        "status": "success",
        "data": list(user_kbs.get(user_id, {}).values())
    }

@router.get("/knowledge-bases/{kb_id}", response_model=Dict)
async def get_knowledge_base(
    kb_id: str,
    current_user: Annotated[UserModel, Depends(get_current_user)]
):
    user_id = current_user.id
    if user_id not in user_kbs or kb_id not in user_kbs[user_id]:
        raise HTTPException(status_code=404, detail="知识库不存在")
    
    return {
        "status": "success",
        "data": user_kbs[user_id][kb_id]
    }

# @CDK: 添加知识库删除功能
@router.delete("/knowledge-bases/{kb_id}", response_model=Dict)
async def delete_knowledge_base(
    kb_id: str,
    current_user: Annotated[UserModel, Depends(get_current_user)]
):
    user_id = current_user.id
    if user_id not in user_kbs or kb_id not in user_kbs[user_id]:
        raise HTTPException(status_code=404, detail="知识库不存在")
    
    kb_info = user_kbs[user_id][kb_id]
    vector_key = f"{user_id}_{kb_id}"
    
    try:
        # 删除向量存储文件
        vector_path = os.path.join(STORAGE_DIR, VECTOR_DIR, f"{vector_key}.pkl")
        if os.path.exists(vector_path):
            os.remove(vector_path)
            print(f"已删除向量存储文件: {vector_path}")
        
        # 删除知识库目录
        if os.path.exists(kb_info["directory"]):
            import shutil
            shutil.rmtree(kb_info["directory"])
            print(f"已删除知识库目录: {kb_info['directory']}")
        
        # 从内存中移除
        if vector_key in vector_stores:
            del vector_stores[vector_key]
        del user_kbs[user_id][kb_id]
        
        # 如果用户没有其他知识库，清理用户记录
        if not user_kbs[user_id]:
            del user_kbs[user_id]
        
        # 保存更新后的元数据
        save_metadata()
        
        return {
            "status": "success",
            "message": "知识库已删除"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除知识库失败: {str(e)}")

# 文档处理接口
@router.post("/knowledge-bases/{kb_id}/documents", response_model=Dict)
async def upload_document(
    current_user: Annotated[UserModel, Depends(get_current_user)],
    kb_id: str,
    file: UploadFile = File(...),
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
        if vector_stores[vector_key] is None:
            # 第一次上传文档，创建向量存储
            print(f"🆕 首次创建向量存储: {vector_key}")
            vector_stores[vector_key] = FAISS.from_documents(split_docs, embeddings)
        else:
            # 向现有向量存储添加文档
            print(f"➕ 向现有向量存储添加文档: {vector_key}")
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
        
        # @CDK: 保存元数据和向量存储到文件
        save_metadata()
        save_vector_store(vector_key, vector_stores[vector_key])
        
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
    current_user: Annotated[UserModel, Depends(get_current_user)]
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
    current_user: Annotated[UserModel, Depends(get_current_user)]
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
    current_user: Annotated[UserModel, Depends(get_current_user)]
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

# 简单的向量存储状态检查
@router.get("/knowledge-bases/{kb_id}/status", response_model=Dict)
async def check_kb_status(
    kb_id: str,
    current_user: Annotated[UserModel, Depends(get_current_user)]
):
    """检查知识库状态"""
    user_id = current_user.id
    vector_key = f"{user_id}_{kb_id}"
    
    if user_id not in user_kbs or kb_id not in user_kbs[user_id]:
        raise HTTPException(status_code=404, detail="知识库不存在")
    
    vector_store = vector_stores.get(vector_key)
    
    if vector_store is None:
        return {"status": "empty", "message": "向量存储为空"}
    
    # 检查文档数量
    doc_count = 0
    if hasattr(vector_store, 'docstore') and hasattr(vector_store.docstore, '_dict'):
        doc_count = len(vector_store.docstore._dict)
    
    return {
        "status": "active", 
        "doc_count": doc_count,
        "vector_key": vector_key
    }

# 供内部调用的检索函数（给question_generator使用）
def retrieve_knowledge(kb_id: str, question: str, top_k: int = 3, user_id: str = None) -> str:
    print(f"\n=== RAG检索调试信息 ===")
    print(f"用户ID: {user_id}")
    print(f"知识库ID: {kb_id}")
    print(f"检索问题: {question}")
    print(f"检索数量: {top_k}")
    
    # 严格 新增用户认证校验
    if not user_id or user_id not in user_kbs or kb_id not in user_kbs[user_id]:
        print("❌ 缺少授权或知识库不存在")
        print(f"user_id存在: {bool(user_id)}")
        print(f"user_id在user_kbs中: {user_id in user_kbs if user_id else False}")
        if user_id and user_id in user_kbs:
            print(f"该用户的知识库: {list(user_kbs[user_id].keys())}")
        return ""  # 无权限或知识库不存在时返回空
    
    vector_key = f"{user_id}_{kb_id}"
    print(f"向量存储键: {vector_key}")
    
    if vector_key not in vector_stores:
        print(f"❌ 向量存储未找到: {vector_key}")
        print(f"可用的向量存储键: {list(vector_stores.keys())}")
        return ""
    
    # 检查向量存储状态
    vector_store = vector_stores[vector_key]
    print(f"向量存储类型: {type(vector_store)}")
    
    # 检查向量存储是否有效
    if vector_store is None:
        print("❌ 向量存储为空，请先上传文档")
        return ""
    
    # 检查向量存储中的文档数量
    try:
        # 尝试获取向量存储的基本信息
        if hasattr(vector_store, 'index_to_docstore_id'):
            doc_count = len(vector_store.index_to_docstore_id)
            print(f"向量存储中的文档数量: {doc_count}")
        else:
            print("⚠️ 无法获取向量存储文档数量")
            doc_count = "未知"
        
        # 检查向量存储是否为空
        if hasattr(vector_store, 'docstore') and hasattr(vector_store.docstore, '_dict'):
            actual_docs = len(vector_store.docstore._dict)
            print(f"实际存储的文档数量: {actual_docs}")
            
            if actual_docs == 0:
                print("❌ 向量存储为空，没有文档被索引")
                return ""
        else:
            print("⚠️ 无法检查向量存储内容")
            
    except Exception as e:
        print(f"⚠️ 检查向量存储状态时出错: {e}")

    # @CDK: 优化检索策略 - 提取专业关键词
    import jieba
    import jieba.analyse
    import re

    def extract_keywords(text):
        """智能关键词提取：
        1. 优先提取 #标签
        2. 若无标签，使用 jieba 提取关键词（基于 TF-IDF）
        3. 结合停用词过滤，支持广泛中文语义
        """
        print(f"🔍 关键词提取调试:")
        print(f"  原始文本: '{text}'")

        # === 阶段一：提取 #标签关键词 ===
        print("  正在尝试提取 #标签...")
        tag_pattern = r'#{1,}\s*([^#\s]+(?:\s[^#\s]+)*)'
        matches = re.findall(tag_pattern, text)
        keywords = [match.strip() for match in matches if match.strip()]

        if keywords:
            result = ' '.join(keywords)
            print(f"  ✅ 成功提取标签关键词: '{result}'")
            return result

        print("  ⚠️ 未检测到标签，进入 jieba 智能关键词提取...")

        # === 阶段二：使用 jieba 提取关键词（自动忽略停用词）===
        # jieba.analyse 自动生成关键词，已内置常用停用词
        # 可设置 topK=5（最多5个），allowPOS 指定保留哪些词性（如名词、动词等）

        # 允许的词性：n=名词, nz=其他名词, v=动词, vn=动名词, eng=英文术语
        allowed_pos = ('n', 'nz', 'v', 'vn', 'eng')

        # 使用 TF-IDF 算法提取关键词，带词性过滤
        keywords = jieba.analyse.extract_tags(
            text,
            topK=6,  # 最多返回6个关键词
            withWeight=False,  # 不返回权重
            allowPOS=allowed_pos  # 只保留指定词性的词
        )

        if keywords:
            result = ' '.join(keywords)
            print(f"  🌟 jieba 提取成功: '{result}'")
            return result

        print("  ⚠️ jieba 未提取到关键词，fallback 到基础清洗...")

        # === 阶段三：基础 fallback（去标点 + 简单过滤）===
        cleaned = re.sub(r'[^\w\s\u4e00-\u9fff]', ' ', text)
        words = cleaned.split()
        fallback = [
            w for w in words
            if len(w) > 1 and not w.isdigit()
        ]

        result = ' '.join(fallback) if fallback else "通用问题"
        print(f"  🛑 使用兜底结果: '{result}'")
        return result
    
    try:
        # 提取专业关键词
        search_query = extract_keywords(question)
        print(f"原始问题: {question}")
        print(f"提取的关键词: {search_query}")
        
        # 使用关键词进行检索 - 增加检索数量并去重
        print(f"🔍 开始关键词检索: '{search_query}'")
        
        # 增加初始检索数量，后续再筛选
        expanded_top_k = min(top_k * 3, 10)  # 最多获取10个结果
        docs = vector_store.similarity_search_with_score(
            search_query, 
            k=expanded_top_k
        )
        
        print(f"关键词检索结果数量: {len(docs)}")
        
        # 如果获取结果不足，使用原问题再次检索补充
        if len(docs) < top_k:
            print(f"🔄 结果不足，使用原问题补充检索: '{question}'")
            additional_docs = vector_store.similarity_search_with_score(
                question, 
                k=top_k - len(docs)
            )
            docs.extend(additional_docs)
        
        # 去重处理
        seen_content = set()
        unique_docs = []
        for doc, score in docs:
            # 基于内容前200字符去重
            content_hash = hash(doc.page_content[:200])
            if content_hash not in seen_content:
                seen_content.add(content_hash)
                unique_docs.append((doc, score))
        
        # 按相似度排序并截取所需数量
        unique_docs.sort(key=lambda x: x[1])  # 分数越低越相似
        final_docs = unique_docs[:top_k]
        
        print(f"去重后最终结果数量: {len(final_docs)}")
        
        if final_docs:
            # 显示检索到的文档内容和相似度分数
            print("📄 检索到的文档内容片段:")
            for i, (doc, score) in enumerate(final_docs):
                content_preview = doc.page_content[:100] + "..." if len(doc.page_content) > 100 else doc.page_content
                print(f"  文档{i+1} (相似度: {score:.3f}): {content_preview}")
            
            # 返回所有检索结果
            content = "\n\n".join([doc.page_content for doc, _ in final_docs])
            print(f"✅ 检索成功，内容长度: {len(content)}")
            return content
        
        print("❌ 所有检索方法都失败")
        return ""
                
    except Exception as e:
        print(f"❌ 检索过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        return ""
