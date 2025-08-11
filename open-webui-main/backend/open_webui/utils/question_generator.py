# edited & created by CDK
# 封装选择题生成逻辑（包括 prompt 构建和大模型调用）
# - 设计 prompt 模板
# - 调用本地模型（如 Ollama，使用 `requests.post`）
# - 解析模型返回，生成标准化 JSON

import requests
import os
import random
from fastapi import Request
from open_webui.utils.parseModelOutput import parse_model_output
# from open_webui.utils.getUserModel import ...

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

test_knowledge = """
https://zh.wikipedia.org/wiki/%E6%A0%B8%E9%85%B8#

核酸（英语：nucleic acid）是一种通常位于细胞内的大型生物分子，主要负责生物体遗传信息的携带和传递。核酸有两大类，分别是脱氧核糖核酸（DNA）和核糖核酸（RNA）。

核酸的单体结构为核苷酸。每一个核苷酸分子由三部分组成：一个五碳糖、一个含氮碱基和一个或多个磷酸基团。如果其五碳糖是脱氧核糖则为脱氧核糖核苷酸，此单体之聚合物是DNA。如果其五碳糖是核糖则为核糖核苷酸，此单体之聚合物是RNA。

核酸是最重要的生物大分子（其余为氨基酸/蛋白质，糖类/碳水化合物和脂质/脂肪）。它们大量存在于所有生物，功能有编码、传递和表达遗传信息。换句话说，遗传消息通过核酸序列被传递。DNA分子含有生物物种的所有遗传信息，为双链分子，其中大多数是链状结构大分子，也有少部分呈环状结构，分子量一般都很大。RNA主要是负责DNA遗传信息的翻译和表达，为单链分子，分子量要比DNA小得多。

核酸存在于所有动植物细胞、微生物和病毒、噬菌体内，是生命的最基本物质之一，对生物的成长、遗传、变异等现象起着重要的决定作用。

研究历史
1869年，核酸被科学家弗雷德里希·米歇尔发现[1]。当时该物质被他称为“核素”。
1880年代早期，阿尔布雷希特·科塞尔进一步纯化了该物质，并发现了其具有高酸性特性。
1889年，理查德·阿尔特曼创造了nucleic acid（核酸）一词。
20世纪早期，阿尔布雷希特·科塞尔与他的两个学生发现核酸由核苷酸组成[4]。但当时科塞尔错误地认为核酸由4种核苷酸的重复单位构成。[5]
1953年，沃森和克里克等人发现了DNA的双螺旋结构。[6]
核酸实验研究构成了现代生物学和医学研究的重要组成部分，形成了基因组和法医学，以及生物技术和制药行业的基础[7][8][9]。

脱氧核糖核酸
主条目：脱氧核糖核酸

脱氧核糖核酸（DNA）。
脱氧核糖核酸（DNA）是由脱氧核糖核苷酸构成的一种核酸。其主要负责生物体遗传信息的携带。组成DNA的碱基有四种：腺嘌呤（A）、鸟嘌呤（G）、胸腺嘧啶（T）与胞嘧啶（C）。DNA主要为双链构成的双螺旋结构，但病毒中也有单链DNA[4]。利用体外分子进化技术，也可合成出类似核酶的脱氧核酶[10]。

核糖核酸
主条目：核糖核酸
核糖核酸（RNA）由核糖核苷酸构成，其功能包括遗传信息的传递与核酶等，而一些病毒使用RNA携带遗传信息。组成RNA的碱基中，尿嘧啶（U）代替了胸腺嘧啶。RNA一般为单链。

核酸类似物
除此之外，也可以通过人工合成出核酸类似物（Nucleic acid analogues）。如肽核酸、锁核酸、GNA、苏糖核酸等。核酸类似物通过不同的分子骨架而与自然产生的DNA或RNA区分开来。

结构和组成
组成
核酸由核苷酸组成，而核苷酸又是由含氮碱基、五碳糖和磷酸基构成。

核苷酸
主条目：核苷酸
核酸的单体结构为核苷酸。每一个核苷酸分子有三部分组成：一个含氮碱基，一个五碳糖和一个或多个磷酸基团。由含氮碱基和五碳糖组成的结构叫做核苷。

碱基
主条目：核碱基
含氮碱基是两种母体分子嘌呤和嘧啶的派生物。一般，组成核酸的碱基有五种，分别是：

腺嘌呤（A）
鸟嘌呤（G）
胞嘧啶（C）
胸腺嘧啶（T，又称5-甲基尿嘧啶[5]，在RNA中一般由尿嘧啶代替）
尿嘧啶（U，在DNA中由胸腺嘧啶代替）
除了以上五种碱基之外，部分核酸还含有特殊碱基。即稀有碱基。

核苷
主条目：核苷
核苷是由含氮碱基和戊糖组成的糖苷[5]。核苷加上一个磷酸基就是核苷酸。
"""


def build_prompt(knowledge, user_instruction, type_instruction="", difficulty=""):
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
        if not difficulty:
            # 随机选择题目难度
            hardness = ["简单", "普通", "易混", "困难"]
            # 对应的概率（权重），顺序对应
            weights = [0.25, 0.4, 0.25, 0.1]

            difficulty = random.choices(hardness, weights=weights, k=1)[0]
        return template.format(knowledge=knowledge, user_instruction=user_instruction, type_instruction=type_instruction, difficulty=difficulty)
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

# 以后可能要添加用户Knowledge接口
def generate_question(request: Request, user_instruction="", type_instruction="", difficulty=""):
    """
    生成题目主函数
    返回: 题目列表（list of questions）返回标准格式：{ "questions": [...] }
    """
    print("generating...")
    # return test_json
    # knowledge = RAG_knowledge() # import from RAG system TODO：接入RAG
    knowledge = test_knowledge

    prompt = build_prompt(knowledge=knowledge, user_instruction=user_instruction, type_instruction=type_instruction, difficulty=difficulty)
    # print("Prompt:", prompt)  # 调试用

    model_output = call_qwen_model(prompt)
    # model_output = await call_model_from_request(request, prompt) # 用于调用用户自定义模型版本，TODO：用户信息无法查询
    print("Model Raw Output:", model_output)  # 调试用

    result = parse_model_output(model_output)
    print("Parsed Result:", result)  # 调试用

    # ✅如果解析结果是字典，并且包含 'questions' 字段
    if isinstance(result, dict) and 'questions' in result and isinstance(result['questions'], list):
        return result['questions']  # 直接返回，TODO：待允许返回多个问题时记得删除筛选

    # ❌ 解析失败，返回默认 test_json（完整结构）
    print("解析失败，返回默认题目")
    return test_json  # 返回完整字典，不是 test_json['questions']，前端需要我返回questions列表，即便只能渲染1个问题




