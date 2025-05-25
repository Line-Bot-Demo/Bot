# EmoBench 測試與自動化

## 目的
說明如何將 EmoBench 評測納入 pytest 測試流程或 CI/CD pipeline。

## pytest 測試範例

```python
# tests/test_emobench_integration.py

from utils.emobench_adapter import predict

def test_predict_joy():
    assert predict("我今天很開心") == "joy"

def test_predict_sadness():
    assert predict("我今天很難過") == "sadness"

def test_predict_neutral():
    assert predict("這是一句普通的話") == "neutral"
```

## CI/CD 自動化建議

- 在 `.github/workflows/ci.yml` 新增如下步驟：

```yaml
- name: Run EmoBench evaluation
  run: |
    cd EmoBench
    pip install -r requirements.txt
    python src/main.py --model_type openai-compatible --model_path http://localhost:8000/predict --lang all --task all --device -1
```

## 排錯建議
- 若測試失敗，請檢查模型 API 是否啟動、路徑是否正確。
- 若遇到相依套件衝突，建議於獨立虛擬環境執行。
