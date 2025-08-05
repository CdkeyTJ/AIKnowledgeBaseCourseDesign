# edited & created by CDK
from fastapi import FastAPI, Request
from .question_generator import generate_question

app = FastAPI()

@app.post("/generate-question")
async def generate_question_api(request: Request):
    data = await request.json()
    prompt = data.get("prompt")
    result = generate_question(prompt)
    return result