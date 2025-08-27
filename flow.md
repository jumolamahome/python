flowchart TD
    start([開始]) --> A[啟動 Playwright]
    A --> B[啟動 Chromium（headless=False）]
    B --> C[開新分頁；viewport=1440×900]
    C --> D[前往 packages.eztravel.com.tw]
    D --> E[主結構載入完成（domcontentloaded）]
    E --> F[等待 1.2 秒]
    F --> G{是否有彈窗？}
    G -->|按到「接受」| H[彈窗已關]
    G -->|沒有| I[無彈窗]
    H --> J[嘗試開啟目的地或熱門目的地區塊]
    I --> J
    J --> M[向下捲動 500px]
    M --> N[開始多手段點擊「洛杉磯」]

    N --> S1[策略1｜CSS has 結構（li > span）｜結果 0 個 → 逾時]
    S1 --> S2[策略2｜Role=listitem 名稱比對｜結果 0 個 → 逾時]
    S2 --> S3[策略3｜get_by_text「洛杉磯」｜結果 1 個 → 可見]
    S3 --> S3a[捲動至可視範圍]
    S3a --> S3b[一般 click 成功]
    S3b --> P[[🎉 成功：已點擊「洛杉磯」]]

    P --> Q[關閉瀏覽器]
    Q --> R([流程結束])
