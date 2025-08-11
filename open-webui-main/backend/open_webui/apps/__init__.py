from .main import router as rag_kb_router

plugin_metadata = {
    "name": "RAG Knowledge Base",
    "description": "个人知识库管理系统，支持文档上传和基于RAG的问答功能",
    "version": "1.0.0",
    "author": "Your Name",
    "routes": [
        {
            "path": "/plugins/rag-knowledge-base",
            "router": rag_kb_router
        }
    ]
}
    