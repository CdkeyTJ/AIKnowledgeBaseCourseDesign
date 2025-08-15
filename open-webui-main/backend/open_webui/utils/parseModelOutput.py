# edited & created by @CDK
import json
import re

##################################################
# new change
##################################################

def preprocess_json_text(text):
    if not isinstance(text, str):
        return text

    # 1. 修复布尔值和 null
    text = re.sub(r'\bTrue\b', 'true', text)
    text = re.sub(r'\bFalse\b', 'false', text)
    text = re.sub(r'\bNone\b', 'null', text)
    text = re.sub(r'\bnull\b', 'null', text)

    # 2. 修复键名：把 { xxx : 或 , xxx : 中的 xxx 替换为 "xxx"
    text = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)(\s*:)', r'\1"\2"\3', text)

    # 3. 修复单引号字符串：把 'xxx' 替换为 "xxx"，但避免破坏转义
    # 简单策略：替换未被转义的单引号包围的内容
    def replace_single_quotes(match):
        # 避免处理已转义的 \'，但这里简化处理
        inner = match.group(1)
        # 把内部的 " 转义，避免冲突
        inner = inner.replace('"', '\\"')
        return f'"{inner}"'

    # 匹配未转义的 '...'（不包含嵌套引号）
    text = re.sub(r"'([^'\n\r\t]*)'", replace_single_quotes, text)

    # 4. 移除末尾可能的分号和多余字符
    text = re.sub(r';\s*$', '', text)
    text = text.strip().rstrip(',;')

    # 5. 确保首尾是 {} 或 []
    if not text.startswith(('{', '[')):
        # 尝试提取第一个 { 到最后一个 } 之间的内容
        match = re.search(r'(\{.*\})|(\[.*\])', text, re.DOTALL)
        if match:
            text = match.group(0)
        else:
            raise ValueError("无法提取有效 JSON 结构")

    return text

def fix_json_escapes(text):
    r"""
    修复 JSON 中的反斜杠转义问题：
    - 将非法的 \x 转为 \\x
    - 保留合法的 \n, \t, \r, \", \\ 等
    """
    temp_replacements = {}

    def save_valid(m):
        key = f"__VALID_{len(temp_replacements)}__"
        temp_replacements[key] = m.group(0)
        return key

    valid_escapes = r'\\[ntrbfb/"\\]'
    text = re.sub(valid_escapes, save_valid, text)

    text = text.replace('\\', '\\\\')

    for key, original in temp_replacements.items():
        text = text.replace(key, original)

    return text

def normalize_question(q):
    if not isinstance(q, dict):
        return None

    # 安全获取 type，确保为字符串
    q_type = str(q.get("type", "choice_question") or "choice_question").strip()

    answer = q.get("answer")

    # 处理不同题型的 answer
    if q_type == "true_false_question":
        # 只有当 answer 是明确的布尔值时才保留，否则 False 更安全
        normalized_answer = bool(answer) if isinstance(answer, bool) else False

    elif q_type == "multiple_choice_question":
        if isinstance(answer, list):
            normalized_answer = answer
        elif isinstance(answer, str):
            # 清理并尝试解析字符串形式的列表
            cleaned = answer.strip()
            if cleaned.startswith('[') and cleaned.endswith(']'):
                try:
                    parsed = json.loads(cleaned.replace("'", '"'))
                    normalized_answer = parsed if isinstance(parsed, list) else []
                except:
                    normalized_answer = []
            else:
                # 尝试解析 "0,1,2" 这样的字符串
                try:
                    normalized_answer = [int(x.strip()) for x in cleaned.split(',') if x.strip().isdigit()]
                except:
                    normalized_answer = []
        else:
            normalized_answer = []

    else:  # choice_question 等单选题型
        if answer is None or answer == "":
            normalized_answer = 0
        else:
            try:
                normalized_answer = int(str(answer))
            except (TypeError, ValueError):
                normalized_answer = 0  # 或可设为 None，但 0 更兼容前端

    return {
        "type": q_type,
        "question": str(q.get("question", "") or "").strip(),
        "options": q.get("options", []) or [],
        "answer": normalized_answer,
        "explanation": str(q.get("explanation", "") or "").strip()
    }

def parse_model_output(output):
    if not isinstance(output, str) or not output.strip():
        return None

    # 提取可能存在的JSON块
    json_blocks = re.findall(r'```(?:json|JSON)?\s*\n(.*?)\n```', output, re.DOTALL)
    if not json_blocks:
        json_match = re.search(r'(\{[\s\S]*\})', output)
        if json_match:
            json_blocks = [json_match.group(1)]
        else:
            return None

    questions = []

    for block in json_blocks:
        try:
            raw_text = block.strip()

            # 预处理文本
            raw_text = preprocess_json_text(raw_text)
            raw_text = fix_json_escapes(raw_text)

            data = json.loads(raw_text)

            # 提取 data.questions.questions
            question_data = data
            for key in ['questions', 'questions']:
                question_data = question_data.get(key, {}) if isinstance(question_data, dict) else None
                if question_data is None:
                    break

            if isinstance(question_data, list):
                for q in question_data:
                    normalized = normalize_question(q)
                    if normalized:
                        questions.append(normalized)
            else:
                print(f"预期问题列表，但得到: {type(question_data)}, 结构可能错误")

        except json.JSONDecodeError as e:
            print(f"JSON 解析失败: {e}, block: {raw_text[:100]}...")
            continue
        except Exception as e:
            print(f"处理题目失败: {e}")
            continue

    return {
        "questions": {
            "type": "question",
            "questions": questions
        }
    }

if __name__ == "__main__":
    # 注意这里的 JSON 格式已修正
    output = '''
    {
        "questions": {
            "type": "question",
            "questions": [
                {
                    "type": "choice_question",
                    "question": "在Python中，用于处理日期和时间的标准库是哪一个？",
                    "options": ["random", "datetime", "time", "date"],
                    "answer": 1,
                    "explanation": "正确答案是 datetime 库。"
                },
                {
                    "type": "true_false_question",
                    "question": "伽罗瓦是美国数学家",
                    "answer": false,
                    "explanation": "伽罗瓦是法国天才数学家。"
                },
                {
                    "type": "multiple_choice_question",
                    "question": "请选择0，2，3",
                    "options": ["磷脂", "DNA", "胆固醇", "蛋白质", "葡萄糖"],
                    "answer": [0, 2, 3],
                    "explanation": "future0"
                }
            ]
        }
    }
    '''

    parsed = parse_model_output(output)
    if is_valid_question_format(parsed):
        print("Yes")

    print(json.dumps(parsed, ensure_ascii=False, indent=2))