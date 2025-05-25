# EmoBench 模型接入範例

## 目的
說明如何讓你的情緒分析模型或 API 能被 EmoBench 測試腳本調用。

## 介面需求
- 必須提供一個 `predict(text: str) -> str` 的函式，或一個可接受 POST 請求的 API endpoint，回傳情緒標籤。

## 範例程式碼（本地 Python 函式）

```python
# utils/emobench_adapter.py

from typing import List

def predict(text: str) -> str:
    """
    接收單一句子，回傳情緒標籤。

    Args:
        text (str): 輸入句子

    Returns:
        str: 預測的情緒標籤
    """
    # 這裡以假設分類器為例
    if "開心" in text:
        return "joy"
    elif "難過" in text:
        return "sadness"
    else:
        return "neutral"
```

## 範例程式碼（API 介面）

```python
# FastAPI 版本
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class TextIn(BaseModel):
    text: str

class LabelOut(BaseModel):
    label: str

@app.post("/predict", response_model=LabelOut)
async def predict_api(data: TextIn):
    # 這裡以假設分類器為例
    if "開心" in data.text:
        label = "joy"
    elif "難過" in data.text:
        label = "sadness"
    else:
        label = "neutral"
    return LabelOut(label=label)
```

## 測試方法
- 可用 pytest 撰寫單元測試，或用 curl 測試 API：
  ```bash
  curl -X POST http://localhost:8000/predict -H "Content-Type: application/json" -d '{"text": "我今天很開心"}'
  ```
