from pathlib import Path
import os

import requests


IMAGE_PATH = Path(
    os.environ.get(
        "TEST_CHAT_IMAGE",
        "/Users/cd-la-067/Downloads/Gemini_Generated_Image_4lw8iw4lw8iw4lw8.png",
    )
)


URL = "http://localhost:8000/v1/agent/messages"


def send_chat(prompt: str, session_id: str | None = None, include_image: bool = False) -> dict:
    data = {"prompt": prompt}
    if session_id:
        data["session_id"] = session_id

    files = []
    if include_image:
        if not IMAGE_PATH.exists():
            raise FileNotFoundError(
                f"图片不存在：{IMAGE_PATH}，请设置 TEST_CHAT_IMAGE 环境变量后重试。"
            )
        files = [("files", (IMAGE_PATH.name, IMAGE_PATH.open("rb"), "image/png"))]

    try:
        response = requests.post(URL, data=data, files=files, timeout=300)
    finally:
        for _, file_info in files:
            file_info[1].close()

    print(f"status={response.status_code}")
    print(response.json())
    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    first = send_chat(
        prompt="分析这张图片的 UI 设计问题，并提出改进建议",
        include_image=True,
    )

    second = send_chat(
        prompt="基于上一次分析，整理成 3 条最重要的改进建议。",
        session_id=first["session_id"],
    )

    print("\n首次会话 session_id:", first["session_id"])
    print("二次会话 session_id:", second["session_id"])
