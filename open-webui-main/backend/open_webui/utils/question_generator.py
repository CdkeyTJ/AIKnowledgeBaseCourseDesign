# edited & created by CDK
# 封装选择题生成逻辑（包括 prompt 构建和大模型调用）
# - 设计 prompt 模板
# - 调用本地模型（如 Ollama，使用 `requests.post`）
# - 解析模型返回，生成标准化 JSON

import requests
import json
import os
import re
import random

test_json = {
    "questions": [
        {
            "type": "choice_question",
            "question": "1+1=？（出现此问题则说明模型回答解析失败）",
            "options": ["A. 0", "B. 1", "C. 2", "D. 3"],
            "answer": 2,
            "explanation": "1+1=2"
        }
        ## 目前看来前端不支持多个问题解析，遂定义为逐问题生成
        # ,
        # {
        #     "type": "choice_question",
        #     "question": "光合作用只能在有阳光的白天进行，夜晚无法进行。",
        #     "options": ["A. ture", "B. false"],
        #     "answer": 1,
        #     "explanation": "光合作用分为两个阶段——光反应和暗反应（卡尔文循环）："
        #                    "光反应需要光能，确实只能在白天进行，其作用是将光能转化为化学能（ATP和NADPH），并释放氧气。"
        #                    "暗反应不需要光，但需要光反应提供的ATP和NADPH。"
        #                    "因此，只要植物体内储存了足够的ATP和NADPH（例如白天积累的），暗反应在夜晚仍可短暂进行。"
        #                    "不过，由于夜晚无法补充能量，光合作用整体会逐渐停止。"
        # }
    ]
}

def build_prompt(subject, difficulty, type_instruction=""):
    # 获取当前脚本的绝对路径
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # 构建 prompt.txt 的绝对路径
    prompt_path = os.path.join(script_dir, 'prompt.txt')

    try:
        # 打开并读取模板文件
        with open(prompt_path, 'r', encoding='utf-8') as f:
            template = f.read()

        if not type_instruction:
            # 随机选择题目类型
            types = ["单选题", "多选题", "判断题"]
            type_instruction = random.choice(types)
        return template.format(subject=subject, difficulty=difficulty, type_instruction=type_instruction)
    except FileNotFoundError:
        raise FileNotFoundError(f"找不到提示文件: {prompt_path}")
    except KeyError as e:
        raise KeyError(f"模板变量错误，请检查 prompt.txt 中是否有未定义的 {{...}}: {e}")
    except Exception as e:
        raise Exception(f"读取或格式化 prompt 失败: {e}")


def call_qwen_model(prompt):
    # 假设本地 Ollama/LMDeploy/其他服务已启动，端口和API需根据实际情况调整
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": "qwen2.5:3b",
        "prompt": prompt,
        "stream": False
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        return data.get("response", "")  # Ollama 返回文本在 "response" 字段
    except Exception as e:
        print(f"调用模型失败: {e}")
        return ""


def fix_json_escapes(text):
    r"""
    修复 JSON 中的反斜杠转义问题：
    - 将非法的 \x 转为 \\x
    - 保留合法的 \n, \t, \r, \", \\ 等
    """
    # 先替换所有已知合法的转义序列，临时标记
    temp_replacements = {}

    def save_valid(m):
        key = f"__VALID_{len(temp_replacements)}__"
        temp_replacements[key] = m.group(0)
        return key

    # 匹配所有合法 JSON 转义
    valid_escapes = r'\\[ntrbfb/"\\]'
    text = re.sub(valid_escapes, save_valid, text)

    # 将剩下的所有 \ 替换为 \\
    text = text.replace('\\', '\\\\')

    # 恢复合法的转义
    for key, original in temp_replacements.items():
        text = text.replace(key, original)

    return text

def preprocess_json_text(text):
    """
    预处理非标准 JSON 文本，修复常见错误：
    - True -> true
    - False -> false
    - None -> null
    - 单引号 '...' -> 双引号 "..."
    """
    if not isinstance(text, str):
        return text

    # 修复布尔值和 null
    text = re.sub(r'\bTrue\b', 'true', text)
    text = re.sub(r'\bFalse\b', 'false', text)
    text = re.sub(r'\bNone\b', 'null', text)

    # 可选：修复单引号（如果模型用了单引号）
    # 注意：仅在简单情况下可用，复杂嵌套建议不用
    # text = re.sub(r"(?<!\\)'", '"', text)

    return text


def parse_model_output(output):
    if not isinstance(output, str) or not output.strip():
        return None

    # 提取 ```json ... ```
    json_blocks = re.findall(r'```(?:json|JSON)?\s*\n(.*?)\n```', output, re.DOTALL)
    if not json_blocks:
        json_match = re.search(r'(\{[\s\S]*\})', output)
        if json_match:
            json_blocks = [json_match.group(1)]
        else:
            return None

    for block in json_blocks:
        try:
            raw_text = block.strip()

            # ✅ 第一步：预处理非标准 JSON（修复 True/False、单引号等）
            raw_text = preprocess_json_text(raw_text)

            # ✅ 第二步：修复反斜杠问题（如 \frac, \sin, \| 等）
            raw_text = fix_json_escapes(raw_text)  # ← 输入是字符串

            # ✅ 第三步：解析 JSON（现在 raw_text 是合法 JSON 字符串）
            data = json.loads(raw_text)  # ← 正确：传字符串

            # ✅ 第四步：处理嵌套结构
            question = data.get('content', data)

            normalized = {
                "type": question.get("type", "choice_question"),
                "question": question.get("question", "").strip(),
                "options": question.get("options", []),
                "explanation": question.get("explanation", "").strip()
            }

            answer = question.get("answer")
            if isinstance(answer, (int, bool)):
                normalized["answer"] = answer
            elif isinstance(answer, list):
                normalized["answer"] = answer
            else:
                normalized["answer"] = 0

            return {"questions": [normalized]}

        except json.JSONDecodeError as e:
            print(f"JSON 解析失败: {e}, block: {raw_text[:100]}...")
            continue
        except Exception as e:
            print(f"处理题目失败: {e}")
            continue

    return None


def generate_question(subject="数学", difficulty="中等", type_instruction=""):
    """
    生成题目主函数
    返回: 题目列表（list of questions）返回标准格式：{ "questions": [...] }
    """


    prompt = build_prompt(subject="高等数学", difficulty="中等", type_instruction=type_instruction)
    # print("Prompt:", prompt)  # 调试用

    model_output = call_qwen_model(prompt)
    print("Model Raw Output:", model_output)  # 调试用

    result = parse_model_output(model_output)
    print("Parsed Result:", result)  # 调试用

    # ✅如果解析结果是字典，并且包含 'questions' 字段
    if isinstance(result, dict) and 'questions' in result and isinstance(result['questions'], list):
        return result['questions']  # 直接返回，TODO：待允许返回多个问题时记得删除筛选

    # ❌ 解析失败，返回默认 test_json（完整结构）
    print("解析失败，返回默认题目")
    return test_json  # 返回完整字典，不是 test_json['questions']，前端需要我返回questions列表，即便只能渲染1个问题




