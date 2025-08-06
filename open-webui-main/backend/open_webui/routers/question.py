# edited & created by @CDK
# 添加API路由
from fastapi import APIRouter, Request
from open_webui.question_generator import generate_question

router = APIRouter()

@router.post("/generate-question")
async def generate_question_api(request: Request):
    data = await request.json()
    subject = data.get("subject", "默认学科")
    difficulty = data.get("difficulty", "中等")
    result = generate_question(subject, difficulty)
    return {
        "code": 0,
        "msg": "success",
        "data": result
    }