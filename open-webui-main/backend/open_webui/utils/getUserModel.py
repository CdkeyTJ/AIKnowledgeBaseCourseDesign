# abandoned, 尝试允许用户选择模型
from open_webui.models.auths import Users  # 导入用户模型
from open_webui.utils.auth import decode_token
from fastapi import Request, APIRouter, HTTPException
import httpx


async def get_current_user(request: Request):
    """获取当前认证用户"""
    # 从 Authorization header 获取 token
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = auth_header.split(" ")[1]
    try:
        # 解码 token 获取用户信息
        user_data = decode_token(token)  # 需要导入 decode_token 函数
        if not user_data or "id" not in user_data:
            raise HTTPException(status_code=401, detail="Invalid token")

        user = Users.get_user_by_id(user_data["id"])
        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        return user
    except Exception as e:
        raise HTTPException(status_code=401, detail="Token validation failed")


async def call_model_from_request(request: Request, prompt: str, model: str = None) -> str:
    """
    从 FastAPI 请求上下文中调用模型，自动获取用户和认证信息
    """
    try:
        # ✅ 正确：直接调用并 await get_current_user
        user = await get_current_user(request)
    except HTTPException:
        # 可以重新抛出或处理
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail="Failed to get user")

    if not user:
        raise HTTPException(status_code=401, detail="User not authenticated")

    final_model = model or getattr(user, "default_model", None) or "qwen2.5:7b"

    payload = {
        "model": final_model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False
    }

    # 调用 Open WebUI 的 API
    async with httpx.AsyncClient(base_url="http://localhost:3000", timeout=60.0) as client:
        try:
            response = await client.post(
                "/api/chat/completions",
                json=payload,
                headers={
                    "Authorization": auth_header,
                    "Content-Type": "application/json"
                }
            )
            response.raise_for_status()
            data = response.json()

            # 提取 content（OpenAI 格式）
            if "choices" in data and len(data["choices"]) > 0:
                return data["choices"][0]["message"]["content"].strip()
            else:
                return ""

        except httpx.HTTPStatusError as e:
            error_detail = e.response.text
            print(f"[Model Call Error] Status={e.response.status_code}, Detail={error_detail}")
            raise HTTPException(status_code=500, detail=f"模型调用失败: {error_detail}")
        except Exception as e:
            print(f"[Model Call Exception] {str(e)}")
            raise HTTPException(status_code=500, detail="内部错误")

# model_output = await call_model_from_request(request, prompt) # 用于调用用户自定义模型版本，TODO：用户信息无法查询