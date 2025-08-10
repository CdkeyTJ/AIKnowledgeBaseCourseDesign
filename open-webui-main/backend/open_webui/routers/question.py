# edited & created by @CDK
# 添加API路由
from fastapi import APIRouter, Request
#from open_webui.utils.question_generator import generate_question

router = APIRouter()

@router.post("/generate-question")
async def generate_question_api(request: Request):
    data = await request.json()
    prompt = data.get("prompt", "")
    # result = generate_question(prompt)
    return {
        "code": 0,
        "msg": "success",
        "data": {
            "type": 'multiple_choice_question',
            "question": '下列哪些分子是组成细胞膜的主要成分？',
            "options": ['磷脂', 'DNA', '胆固醇', '蛋白质', '葡萄糖'],
            "answer": [0, 2, 3],
            "explanation": '细胞膜的主要成分包括磷脂双分子层、膜蛋白，以及一定量的胆固醇，起到结构稳定和流动性调节作用。'
        }
    }