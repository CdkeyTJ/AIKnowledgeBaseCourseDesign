// @CDK: RAG知识库管理API
import { WEBUI_BASE_URL } from '$lib/constants';

// 知识库数据结构
export interface KnowledgeBase {
    id: string;
    name: string;
    description: string;
    directory: string;
    created_at: string;
    documents: Document[];
}

export interface Document {
    id: string;
    filename: string;
    file_type: string;
    size: number;
    uploaded_at: string;
    chunks: number;
}

// 创建知识库
export const createKnowledgeBase = async (
    token: string,
    name: string,
    description: string = ""
): Promise<KnowledgeBase> => {
    const res = await fetch(`${WEBUI_BASE_URL}/api/v1/rag/knowledge-bases`, {
        method: 'POST',
        headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
            name,
            description
        })
    });

    if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || '创建知识库失败');
    }

    const data = await res.json();
    return data.data;
};

// 获取用户知识库列表
export const getUserKnowledgeBases = async (token: string): Promise<KnowledgeBase[]> => {
    const res = await fetch(`${WEBUI_BASE_URL}/api/v1/rag/knowledge-bases`, {
        method: 'GET',
        headers: {
            'Accept': 'application/json',
            'Authorization': `Bearer ${token}`
        }
    });

    if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || '获取知识库列表失败');
    }

    const data = await res.json();
    return data.data || [];
};

// 获取特定知识库详情
export const getKnowledgeBase = async (token: string, kbId: string): Promise<KnowledgeBase> => {
    const res = await fetch(`${WEBUI_BASE_URL}/api/v1/rag/knowledge-bases/${kbId}`, {
        method: 'GET',
        headers: {
            'Accept': 'application/json',
            'Authorization': `Bearer ${token}`
        }
    });

    if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || '获取知识库详情失败');
    }

    const data = await res.json();
    return data.data;
};

// 上传文档到知识库
export const uploadDocument = async (
    token: string,
    kbId: string,
    file: File
): Promise<Document> => {
    const formData = new FormData();
    formData.append('file', file);

    const res = await fetch(`${WEBUI_BASE_URL}/api/v1/rag/knowledge-bases/${kbId}/documents`, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${token}`
        },
        body: formData
    });

    if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || '上传文档失败');
    }

    const data = await res.json();
    return data.data;
};

// 获取知识库中的文档列表
export const getKnowledgeBaseDocuments = async (token: string, kbId: string): Promise<Document[]> => {
    const res = await fetch(`${WEBUI_BASE_URL}/api/v1/rag/knowledge-bases/${kbId}/documents`, {
        method: 'GET',
        headers: {
            'Accept': 'application/json',
            'Authorization': `Bearer ${token}`
        }
    });

    if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || '获取文档列表失败');
    }

    const data = await res.json();
    return data.data || [];
};

// 删除知识库中的文档
export const deleteDocument = async (token: string, kbId: string, docId: string): Promise<void> => {
    const res = await fetch(`${WEBUI_BASE_URL}/api/v1/rag/knowledge-bases/${kbId}/documents/${docId}`, {
        method: 'DELETE',
        headers: {
            'Authorization': `Bearer ${token}`
        }
    });

    if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || '删除文档失败');
    }
};

// 查询知识库
export const queryKnowledgeBase = async (
    token: string,
    kbId: string,
    question: string,
    topK: number = 3
): Promise<{ context: string; sources: any[] }> => {
    const res = await fetch(`${WEBUI_BASE_URL}/api/v1/rag/knowledge-bases/${kbId}/query`, {
        method: 'POST',
        headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
            question,
            top_k: topK
        })
    });

    if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || '查询知识库失败');
    }

    const data = await res.json();
    return data.data;
};

// 删除知识库
export const deleteKnowledgeBase = async (
    token: string,
    kbId: string
): Promise<{ status: string; message: string }> => {
    const res = await fetch(`${WEBUI_BASE_URL}/api/v1/rag/knowledge-bases/${kbId}`, {
        method: 'DELETE',
        headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
        }
    });

    if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || '删除知识库失败');
    }

    return res.json();
};
