project/
├── utils/
│   ├── text_processor.py      # 文字正規化與基礎工具
│   ├── file_reader.py         # 檔案讀取
│   └── section_detector.py    # 參考文獻區段識別
│
├── citation/
│   ├── in_text_extractor.py   # 內文引用擷取
│   └── citation_matcher.py    # 引用比對工具
│
├── parsers/
│   ├── ieee/
│   │   ├── ieee_parser.py     # IEEE 完整解析
│   │   ├── ieee_merger.py     # IEEE 斷行合併
│   │   └── ieee_converter.py  # IEEE 格式轉換
│   │
│   └── apa/
│       ├── apa_parser_en.py   # 英文 APA 解析
│       ├── apa_parser_zh.py   # 中文 APA 解析
│       ├── apa_merger.py      # APA 斷行合併與頭部偵測
│       └── apa_converter.py   # APA 格式轉換
│
├── ui/
│   ├── components.py          # UI 元件（統計卡片、文獻顯示）
│   ├── file_upload.py         # 檔案上傳與處理邏輯
│   └── comparison_ui.py       # 比對結果顯示
│
├── checker.py                 # 比對邏輯
├── storage.py                 # Session state
├── reference_router.py        # 路由器
└── app.py                     # 主程式