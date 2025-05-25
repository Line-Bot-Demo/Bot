# EmoBench 整合說明文件

## 目的
本文件說明如何將 EmoBench 評測流程整合進本專案，並用於評估情緒分析模型的表現。

## EmoBench 介紹
EmoBench 是一套專為大型語言模型（LLM）設計的情緒智力評測工具，涵蓋情緒理解與應用兩大任務，支援中英文。

## 安裝與下載
1. 下載 EmoBench 原始碼：
   ```bash
   git clone https://github.com/Sahandfer/EmoBench.git
   ```
2. 安裝必要套件（建議於虛擬環境中執行）：
   ```bash
   cd EmoBench
   pip install -r requirements.txt
   ```

## 將本專案模型接入 EmoBench
1. 於 `/utils/emobench_adapter.py` 實作模型介面（詳見 model_adapter_example.md）。
2. 修改 EmoBench 的 `src/main.py`，將 `--model_type` 設為 `openai-compatible` 或自訂型態，並指定你的 API endpoint 或模型路徑。

## 執行評測
```bash
python src/main.py \
  --model_type openai-compatible \
  --model_path http://localhost:8000/predict \
  --lang all \
  --task all \
  --device -1
```
> 請依照你的模型服務實際 endpoint 調整 `--model_path`。

## 評測結果解讀
- EmoBench 會輸出各項任務的準確率、F1 分數等指標。
- 詳細結果可於 EmoBench 的 `results/` 目錄下查閱。

## 自動化建議
- 可將上述指令寫入 shell script 或納入 CI/CD pipeline。
- 失敗時自動通知開發者。

## 常見問題
- 若遇到相依套件衝突，建議於獨立虛擬環境執行。
- 若模型 API 無法被 EmoBench 調用，請檢查介面格式與回傳格式。
