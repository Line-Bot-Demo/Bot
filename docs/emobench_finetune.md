# EmoBench 進階應用與微調

## 目的
說明如何用 EmoBench 的資料集微調你的模型，提升情緒智力。

## 資料集格式
- EmoBench 提供 JSON/CSV 格式的情緒標註資料，詳見其 `data/` 目錄。

## 微調步驟
1. 下載資料集
2. 依照你的模型格式轉換資料
3. 使用 transformers、pytorch-lightning 等工具進行微調

## 微調後評測
- 微調完成後，重新執行 EmoBench 評測，觀察分數提升情形。
