import requests

def generate_question(topic: str, model_name: str = "qwen2.5:3b"):
    prompt = f"""
请根据以下知识点生成一道单选题，要求包括四个选项和正确答案及解释：

{{
  "question": "问题文本",
  "options": {{
    "A": "选项A",
    "B": "选项B",
    "C": "选项C",
    "D": "选项D"
  }},
  "answer": "正确选项标识符（如 A, B, C, D）",
  "explanation": "简要解释为什么选这个答案"
}}

知识点：{topic}
"""
    
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": model_name,
            "prompt": prompt,
            "max_tokens": 200  # 可调整以适应输出长度
        }
    )
    
    if response.status_code == 200:
        return response.json()['choices'][0]['text'].strip()
    else:
        raise Exception(f"Error generating question: {response.text}")