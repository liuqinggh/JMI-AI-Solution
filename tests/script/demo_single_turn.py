import requests


URL = "http://localhost:8000/v1/agent/messages"


def run_once(prompt: str) -> dict:
    response = requests.post(URL, files={"prompt": (None, prompt)}, timeout=300)
    print(f"status={response.status_code}")
    print(response.json())
    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    run_once("请概述当前服务的职责，并给出 3 条优化建议。")
