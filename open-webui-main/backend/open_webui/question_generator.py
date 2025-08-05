# edited & created by CDK
# - 设计 prompt 模板
# - 调用本地模型（如 Ollama，使用 `requests.post`）
# - 解析模型返回，生成标准化 JSON

import requests

def generate_question(prompt):
    # 调用本地 Ollama 模型
    response = requests.post("http://localhost:11434/api/generate", json={"prompt": prompt})
    # 解析模型返回，生成标准化 JSON
    # 这里假设模型返回已经是标准格式
    return response.json()