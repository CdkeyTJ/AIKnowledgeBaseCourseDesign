# edited & created by @CDK
# 添加API路由
from fastapi import APIRouter, Request
#from open_webui.utils.question_generator import generate_question
from open_webui.utils.question_generator import generate_question

router = APIRouter()

# @CDK: 疑似路由重复
@router.post("/generate-question")
async def generate_question_api(request: Request):
    data = await request.json()
    result = generate_question(data)
    return {
        "code": 0,
        "msg": "success",
        "data": result
    }