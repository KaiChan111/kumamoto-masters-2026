# 熊本大師賽 2026｜中文觀賽表 V2（自動同步測試版）

這是獨立於九州旅行網站的 GitHub Pages 專案。

## 上線

1. 建立新的 **Public** GitHub repository。
2. 把本 ZIP 解壓縮後的**所有檔案及資料夾**上傳至 repo 根目錄（包含隱藏的 `.github/workflows/sync.yml`）。
3. Settings → Pages → Deploy from a branch → `main` → `/ (root)` → Save。
4. Settings → Actions → General → Workflow permissions：確認 Actions 有權寫入 repository contents（workflow 另設 `contents: write`，但 repo 設定或分支保護仍可能限制）。
5. Actions → `Sync BWF schedule` → Run workflow，檢查結果及 `data/sync-status.json`。

## 自動更新原理

- GitHub Actions 在 UTC 每小時 07、37 分排程執行（約每 30 分鐘，**不保證準點**）。
- 抓取 BWF 官方每日賽程 HTML，抽取場次、時間、場地、對戰與英文姓名，套用已建立的中文姓名對照；保留人工標記的推薦與已核對的中文名。
- 寫入 `data/YYYY-MM-DD.json`；網頁在開啟或點「更新」時讀取資料。
- 若抓取失敗、官方改用 JavaScript 動態載入或拒絕 GitHub Actions，**不覆蓋最後成功資料**；Actions 顯示失敗，`data/sync-status.json` 顯示失敗日期。
- 此版本**未驗證 GitHub Actions 能從 BWF 成功取得網頁**，目前只能確認解析器可解析你提供的官方 MHTML 存檔。若 Actions 執行失敗，須研究 BWF 正式資料端點或其他授權來源，不能宣稱已自動同步。
- `data/2026-11-11.json` 已預載 59 場，其他日期需同步成功才會顯示。
- 時間是預估，網站不是即時比分服務。

## 本機驗證

`pip install -r requirements.txt`

`python scripts/sync.py 2026-11-11`

注意：若在無網路的環境執行，會失敗，並保留原始賽程。
