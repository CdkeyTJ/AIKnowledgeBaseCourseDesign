<script lang="ts">
    import { createEventDispatcher } from 'svelte';
    import { toast } from 'svelte-sonner';
    import type { KnowledgeBase, Document } from '$lib/apis/rag';
    import {
        createKnowledgeBase,
        getUserKnowledgeBases,
        uploadDocument,
        getKnowledgeBaseDocuments,
        deleteDocument,
        deleteKnowledgeBase
    } from '$lib/apis/rag';

    const dispatch = createEventDispatcher();

    export let token: string = '';
    export let selectedKbId: string | null = null;

    let knowledgeBases: KnowledgeBase[] = [];
    let selectedKnowledgeBase: KnowledgeBase | null = null;
    let documents: Document[] = [];
    let loading = false;
    let showCreateForm = false;
    let showUploadForm = false;

    // 创建知识库表单
    let newKbName = '';
    let newKbDescription = '';

    // 上传文档表单
    let selectedFile: File | null = null;
    let uploadProgress = 0;

    // 初始化
    $: if (token) {
        loadKnowledgeBases();
    }

    // 加载知识库列表
    const loadKnowledgeBases = async () => {
        try {
            loading = true;
            knowledgeBases = await getUserKnowledgeBases(token);
            
            // 如果有选中的知识库，加载其文档
            if (selectedKbId) {
                await loadDocuments(selectedKbId);
            }
        } catch (error) {
            toast.error(`加载知识库失败: ${error.message}`);
        } finally {
            loading = false;
        }
    };

    // 加载文档列表
    const loadDocuments = async (kbId: string) => {
        try {
            documents = await getKnowledgeBaseDocuments(token, kbId);
            selectedKnowledgeBase = knowledgeBases.find(kb => kb.id === kbId) || null;
        } catch (error) {
            toast.error(`加载文档失败: ${error.message}`);
        }
    };

    // 创建知识库
    const handleCreateKnowledgeBase = async () => {
        if (!newKbName.trim()) {
            toast.error('请输入知识库名称');
            return;
        }

        try {
            const newKb = await createKnowledgeBase(token, newKbName.trim(), newKbDescription.trim());
            knowledgeBases = [...knowledgeBases, newKb];
            
            // 清空表单
            newKbName = '';
            newKbDescription = '';
            showCreateForm = false;
            
            toast.success('知识库创建成功');
        } catch (error) {
            toast.error(`创建知识库失败: ${error.message}`);
        }
    };

    // 选择知识库
    const handleSelectKnowledgeBase = async (kbId: string | null) => {
        selectedKbId = kbId;
        dispatch('kbSelected', { kbId });
        
        if (kbId) {
            await loadDocuments(kbId);
        } else {
            documents = [];
            selectedKnowledgeBase = null;
        }
    };

    // 上传文档
    const handleFileSelect = (event: Event) => {
        const target = event.target as HTMLInputElement;
        if (target.files && target.files.length > 0) {
            selectedFile = target.files[0];
        }
    };

    const handleUploadDocument = async () => {
        if (!selectedFile || !selectedKbId) {
            toast.error('请选择文件和知识库');
            return;
        }

        try {
            showUploadForm = false;
            uploadProgress = 0;
            
            // 模拟上传进度
            const progressInterval = setInterval(() => {
                uploadProgress += 10;
                if (uploadProgress >= 90) clearInterval(progressInterval);
            }, 100);

            const newDoc = await uploadDocument(token, selectedKbId, selectedFile);
            documents = [...documents, newDoc];
            
            clearInterval(progressInterval);
            uploadProgress = 100;
            
            // 更新知识库文档计数
            if (selectedKnowledgeBase) {
                selectedKnowledgeBase.documents = documents;
                knowledgeBases = knowledgeBases.map(kb => 
                    kb.id === selectedKbId ? selectedKnowledgeBase! : kb
                );
            }
            
            selectedFile = null;
            toast.success('文档上传成功');
            
            setTimeout(() => {
                uploadProgress = 0;
            }, 1000);
        } catch (error) {
            toast.error(`上传文档失败: ${error.message}`);
        }
    };

    // 删除文档
    const handleDeleteDocument = async (docId: string) => {
        if (!selectedKbId) return;
        
        if (!confirm('确定要删除这个文档吗？')) return;
        
        try {
            await deleteDocument(token, selectedKbId, docId);
            documents = documents.filter(doc => doc.id !== docId);
            
            // 更新知识库文档计数
            if (selectedKnowledgeBase) {
                selectedKnowledgeBase.documents = documents;
                knowledgeBases = knowledgeBases.map(kb => 
                    kb.id === selectedKbId ? selectedKnowledgeBase! : kb
                );
            }
            
            toast.success('文档删除成功');
        } catch (error) {
            toast.error(`删除文档失败: ${error.message}`);
        }
    };

    // 删除知识库
    const handleDeleteKnowledgeBase = async (kbId: string) => {
        if (!selectedKbId) return;

        if (!confirm('确定要删除这个知识库吗？')) return;

        try {
            await deleteKnowledgeBase(token, kbId);
            knowledgeBases = knowledgeBases.filter(kb => kb.id !== kbId);
            selectedKbId = null;
            documents = [];
            selectedKnowledgeBase = null;
            toast.success('知识库删除成功');
        } catch (error) {
            toast.error(`删除知识库失败: ${error.message}`);
        }
    };

    // @CDK: 检查向量存储状态
    const checkVectorStoreStatus = async () => {
        if (!selectedKbId) return;
        
        try {
            const response = await fetch(`/api/rag/knowledge-bases/${selectedKbId}/status`, {
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });
            
            if (response.ok) {
                const result = await response.json();
                console.log('知识库状态:', result);
                
                if (result.status === 'empty') {
                    toast.warning('向量存储为空，请先上传文档');
                } else if (result.status === 'active') {
                    toast.success(`知识库正常，包含 ${result.doc_count} 个文档`);
                    console.log('状态详情:', result);
                } else {
                    toast.error(`知识库状态异常: ${result.message}`);
                }
            } else {
                toast.error('检查知识库状态失败');
            }
        } catch (error) {
            toast.error(`检查失败: ${error.message}`);
        }
    };

    // 格式化文件大小
    const formatFileSize = (bytes: number): string => {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    };

    // 格式化日期
    const formatDate = (dateString: string): string => {
        return new Date(dateString).toLocaleDateString('zh-CN');
    };
</script>

<div class="knowledge-base-manager bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6 max-w-4xl mx-auto">
    <div class="flex justify-between items-center mb-6">
        <h2 class="text-2xl font-bold text-gray-900 dark:text-white">知识库管理</h2>
        <div class="flex gap-2">
            <button
                on:click={() => showCreateForm = !showCreateForm}
                class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
            >
                {showCreateForm ? '取消' : '创建知识库'}
            </button>
            <button
                on:click={() => showUploadForm = !showUploadForm}
                disabled={!selectedKbId}
                class="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
                {showUploadForm ? '取消' : '上传文档'}
            </button>
            <!-- @CDK: 添加检查向量存储状态按钮 -->
            <button
                on:click={() => checkVectorStoreStatus()}
                disabled={!selectedKbId}
                class="px-4 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
                检查状态
            </button>
        </div>
    </div>

    <!-- 创建知识库表单 -->
    {#if showCreateForm}
        <div class="mb-6 p-4 border border-gray-200 dark:border-gray-700 rounded-lg">
            <h3 class="text-lg font-semibold mb-4 text-gray-900 dark:text-white">创建新知识库</h3>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                    <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        知识库名称 *
                    </label>
                    <input
                        type="text"
                        bind:value={newKbName}
                        placeholder="输入知识库名称"
                        class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
                    />
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        描述
                    </label>
                    <input
                        type="text"
                        bind:value={newKbDescription}
                        placeholder="输入知识库描述"
                        class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
                    />
                </div>
            </div>
            <div class="mt-4">
                <button
                    on:click={handleCreateKnowledgeBase}
                    class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
                >
                    创建知识库
                </button>
            </div>
        </div>
    {/if}

    <!-- 上传文档表单 -->
    {#if showUploadForm && selectedKbId}
        <div class="mb-6 p-4 border border-gray-200 dark:border-gray-700 rounded-lg">
            <h3 class="text-lg font-semibold mb-4 text-gray-900 dark:text-white">上传文档到知识库</h3>
            <div class="mb-4">
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    选择文件 (支持 PDF, TXT)
                </label>
                <input
                    type="file"
                    accept=".pdf,.txt"
                    on:change={handleFileSelect}
                    class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
                />
            </div>
            {#if selectedFile}
                <div class="mb-4 p-2 bg-gray-100 dark:bg-gray-700 rounded">
                    <p class="text-sm text-gray-700 dark:text-gray-300">
                        已选择: {selectedFile.name} ({formatFileSize(selectedFile.size)})
                    </p>
                </div>
            {/if}
            {#if uploadProgress > 0}
                <div class="mb-4">
                    <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                        <div class="bg-blue-600 h-2 rounded-full transition-all duration-300" style="width: {uploadProgress}%"></div>
                    </div>
                    <p class="text-sm text-gray-600 dark:text-gray-400 mt-1">上传进度: {uploadProgress}%</p>
                </div>
            {/if}
            <div class="flex gap-2">
                <button
                    on:click={handleUploadDocument}
                    disabled={!selectedFile}
                    class="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    上传文档
                </button>
            </div>
        </div>
    {/if}

    <!-- 知识库列表 -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- 左侧：知识库列表 -->
        <div class="lg:col-span-1">
            <h3 class="text-lg font-semibold mb-4 text-gray-900 dark:text-white">我的知识库</h3>
            {#if loading}
                <div class="text-center py-8">
                    <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
                    <p class="text-gray-500 dark:text-gray-400 mt-2">加载中...</p>
                </div>
            {:else if knowledgeBases.length === 0}
                <div class="text-center py-8 text-gray-500 dark:text-gray-400">
                    <p>暂无知识库</p>
                    <p class="text-sm mt-1">点击上方按钮创建您的第一个知识库</p>
                </div>
            {:else}
                <div class="space-y-3">
                    {#each knowledgeBases as kb}
                        <div
                            class="p-4 border rounded-lg cursor-pointer transition-all hover:shadow-md {selectedKbId === kb.id ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20' : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'}"
                            on:click={() => handleSelectKnowledgeBase(kb.id)}
                        >
                            <div class="flex justify-between items-start">
                                <div class="flex-1">
                                    <h4 class="font-medium text-gray-900 dark:text-white">{kb.name}</h4>
                                    {#if kb.description}
                                        <p class="text-sm text-gray-600 dark:text-gray-400 mt-1">{kb.description}</p>
                                    {/if}
                                    <p class="text-xs text-gray-500 dark:text-gray-500 mt-2">
                                        文档: {kb.documents?.length || 0} | 创建: {formatDate(kb.created_at)}
                                    </p>
                                </div>
                                <!-- @CDK: 添加删除知识库按钮 -->
                                <button
                                    on:click|stopPropagation={() => handleDeleteKnowledgeBase(kb.id)}
                                    class="px-2 py-1 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-md transition-colors text-sm"
                                    title="删除知识库"
                                >
                                    删除
                                </button>
                            </div>
                        </div>
                    {/each}
                </div>
            {/if}
        </div>

        <!-- 右侧：文档列表 -->
        <div class="lg:col-span-2">
            {#if selectedKnowledgeBase}
                <div class="mb-4">
                    <h3 class="text-lg font-semibold text-gray-900 dark:text-white">
                        {selectedKnowledgeBase.name} - 文档列表
                    </h3>
                    <p class="text-sm text-gray-600 dark:text-gray-400">
                        共 {documents.length} 个文档
                    </p>
                </div>
                
                {#if documents.length === 0}
                    <div class="text-center py-8 text-gray-500 dark:text-gray-400">
                        <p>该知识库暂无文档</p>
                        <p class="text-sm mt-1">点击上方"上传文档"按钮添加文档</p>
                    </div>
                {:else}
                    <div class="space-y-3">
                        {#each documents as doc}
                            <div class="p-4 border border-gray-200 dark:border-gray-700 rounded-lg">
                                <div class="flex justify-between items-start">
                                    <div class="flex-1">
                                        <h4 class="font-medium text-gray-900 dark:text-white">{doc.filename}</h4>
                                        <div class="flex gap-4 text-sm text-gray-600 dark:text-gray-400 mt-2">
                                            <span>类型: {doc.file_type.toUpperCase()}</span>
                                            <span>大小: {formatFileSize(doc.size)}</span>
                                            <span>分块: {doc.chunks}</span>
                                            <span>上传: {formatDate(doc.uploaded_at)}</span>
                                        </div>
                                    </div>
                                    <button
                                        on:click={() => handleDeleteDocument(doc.id)}
                                        class="px-3 py-1 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-md transition-colors"
                                    >
                                        删除
                                    </button>
                                </div>
                            </div>
                        {/each}
                    </div>
                {/if}
            {:else}
                <div class="text-center py-8 text-gray-500 dark:text-gray-400">
                    <p>请选择一个知识库查看文档</p>
                </div>
            {/if}
        </div>
    </div>
</div>
