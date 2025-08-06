# edited & created by CDK
# 封装选择题生成逻辑（包括 prompt 构建和大模型调用）
# - 设计 prompt 模板
# - 调用本地模型（如 Ollama，使用 `requests.post`）
# - 解析模型返回，生成标准化 JSON

import requests

def build_prompt(subject, difficulty):
    # 可从 prompt.txt 读取模板
    with open('prompt.txt', 'r', encoding='utf-8') as f:
        template = f.read()
    return template.format(subject=subject, difficulty=difficulty)

def call_qwen_model(prompt):
    # 假设本地 Ollama/LMDeploy/其他服务已启动，端口和API需根据实际情况调整
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": "qwen2.5:3b",
        "prompt": prompt,
        "stream": False
    }
    response = requests.post(url, json=payload)
    response.raise_for_status()
    return response.json()["response"]  # 视实际返回结构调整

def parse_model_output(output):
    # 假设模型输出已是标准JSON，否则需正则/字符串处理
    import json
    return json.loads(output)

def generate_question(subject, difficulty):
    prompt = build_prompt(subject, difficulty)
    model_output = call_qwen_model(prompt)
    return parse_model_output(model_output)

    