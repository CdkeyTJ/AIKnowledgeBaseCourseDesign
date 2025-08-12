
import json
import re

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
