from typing import List

def predict(text: str) -> str:
    """
    接收單一句子，回傳情緒標籤。

    Args:
        text (str): 輸入句子

    Returns:
        str: 預測的情緒標籤
    """
    # TODO: 替換為你的模型推論邏輯
    if "開心" in text:
        return "joy"
    elif "難過" in text:
        return "sadness"
    else:
        return "neutral"
