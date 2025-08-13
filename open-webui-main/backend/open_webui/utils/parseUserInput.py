# edited & created by @CDK
import random
import re

# ======================
# 数字识别（中文、英文、阿拉伯）
# ======================

# 中文数字（支持：一、二、...、二十）
CN_NUM = r'零|一|二|两|三|四|五|六|七|八|九|十|十一|十二|十三|十四|十五|十六|十七|十八|十九|二十'

# 英文数字（支持：one, two, ..., twenty）
EN_NUM = r'zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty'

# 阿拉伯数字
ARABIC_NUM = r'\d+'

# 统一数字模式
NUMBER_PATTERN = f'({CN_NUM}|{EN_NUM}|{ARABIC_NUM})'

# ======================
# 量词识别（支持中英文）
# ======================
QUANTIFIERS = r'(?:道|个|题|条|次|回|批|组|份|个|of|questions?|items?|problems?|questions?)?'

# ======================
# 题型关键词映射（中英文 → 内部类型）
# ======================

# 中文题型关键词
CN_QUESTION_TYPES = r'单选|多选|选择|判断|填空|简答|问答|主观|客观|不定项选择'

# 英文题型关键词 → 内部分类（用于匹配）
EN_QUESTION_TYPES_RAW = [
    'single choice', 'multiple choice', 'multiple-choice',
    'true or false', 'true/false', 'judgment', 'judgement',
    'selection', 'select', 'question'
]

# 转义后用于正则
EN_QUESTION_TYPES_REGEX = '|'.join(re.escape(t) for t in EN_QUESTION_TYPES_RAW)

# 完整题型正则（中英混合）
QUESTION_TYPE_PATTERN = f'({CN_QUESTION_TYPES}|{EN_QUESTION_TYPES_REGEX})'

# ======================
# 主正则表达式（支持中英混合）
# ======================
PATTERN = rf'''
(?P<number>{NUMBER_PATTERN})           # 数字
\s*
(?P<quantifier>{QUANTIFIERS})          # 量词
\s*
(?P<type>{QUESTION_TYPE_PATTERN})      # 题型
'''

QUESTION_REGEX = re.compile(PATTERN, re.IGNORECASE | re.VERBOSE)

# 编译正则（忽略大小写 + 多行模式）
QUESTION_REGEX = re.compile(PATTERN, re.IGNORECASE | re.VERBOSE)


# ======================
# 中英文数字转整数
# ======================
def text_to_number(num_text: str) -> int:
    """
    将中文、英文或阿拉伯数字字符串转为整数
    """
    num_text = num_text.strip().lower()

    # 阿拉伯数字
    if num_text.isdigit():
        return int(num_text)

    # 中文数字映射
    cn_map = {
        '零': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4,
        '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
        '十一': 11, '十二': 12, '十三': 13, '十四': 14, '十五': 15,
        '十六': 16, '十七': 17, '十八': 18, '十九': 19, '二十': 20
    }
    if num_text in cn_map:
        return cn_map[num_text]

    # 英文数字映射
    en_map = {
        'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4,
        'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
        'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15,
        'sixteen': 16, 'seventeen': 17, 'eighteen': 18, 'nineteen': 19, 'twenty': 20
    }
    if num_text in en_map:
        return en_map[num_text]

    return 0  # 默认为1


# ======================
# 题型关键词归一化 → 内部类型
# ======================
def normalize_question_type(type_text: str) -> str:
    """
    将中英文题型关键词归一化为内部类型：'single', 'multi', 'truefalse', 'choice'
    """
    type_text = type_text.lower().strip()

    # 中文判断
    if "单选" in type_text:
        return 'single'
    if "多选" in type_text or "不定项选择" in type_text:
        return 'multi'
    if "判断" in type_text:
        return 'truefalse'

    # 英文判断
    if "single choice" in type_text:
        return 'single'
    if "multiple choice" in type_text or "multiple-choice" in type_text:
        return 'multi'
    if "true or false" in type_text or "true/false" in type_text or "judg" in type_text:
        return 'truefalse'
    if "selection" in type_text or "select" in type_text or "question" in type_text:
        return 'single'

    return 'single'  # 默认


# ======================
# 主函数：提取题目数量与类型
# ======================
def extract_question_numbers(text: str):
    """
    从用户输入中提取题目数量与类型
    返回字典：{
        "single_num": 0,
        "multi_num": 0,
        "truefalse_num": 0,
    }
    """
    # 初始化计数
    result = {
        "single_num": 0,
        "multi_num": 0,
        "truefalse_num": 0,
    }

    if not text or not isinstance(text, str):
        return result

    # 使用 finditer → 返回 Match 对象迭代器
    matches = QUESTION_REGEX.finditer(text)

    for match in matches:
        num_str = match.group('number').strip()
        type_str = match.group('type').strip()

        num = text_to_number(num_str)
        q_type = normalize_question_type(type_str)

        # 累加到对应字段
        if q_type == 'single':
            result["single_num"] += num
        elif q_type == 'multi':
            result["multi_num"] += num
        elif q_type == 'truefalse':
            result["truefalse_num"] += num

    return result

def parse_input_demand(request_data):
    text = request_data.get("prompt", "")

    # 难度匹配
    difficulty_pattern = r"(简单|普通|易混|困难)"
    match_difficulty = re.search(difficulty_pattern, text)
    if match_difficulty:
        difficulty = match_difficulty.group(1)
    else:
        # 如果没有找到难度，默认随机选择
        hardness = ["简单", "普通", "易混", "困难"]
        weights = [0.25, 0.4, 0.25, 0.1]
        difficulty = random.choices(hardness, weights=weights, k=1)[0]
    NumberOfQuestions = extract_question_numbers(text)

    return difficulty, NumberOfQuestions, text

# 测试
if __name__ == "__main__":
    test_cases = [
        "3 single choice",
        "1 true or false question",
        "2 multiple choice",
        "give me five selection questions",
        "出三道多选题和1个true or false",
        "generate one single choice",
        "please give me 4 judgment questions",
        "I want two 填空题 and 1 multiple choice",
        "请出五题简答"
    ]

    for case in test_cases:
        result = extract_question_numbers(case)
        print(f"{case:40} → {result}")