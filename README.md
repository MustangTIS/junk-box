# Junk-Box

日々のメンテナンスやちょっとした整理・作業を効率化するための、自作スクリプト（Python / PowerShell）の個人用ツール箱です。

## 📂 収録ツール一覧

### 🎵 Audio Tools (`audio-tools/`)
* **audio-size-merger**
  * 2つのフォルダ構造を比較し、ファイルサイズが大きい方（高品質な側）を優先して安全に上書き・統合するツール。
* **flac-mp3-cleaner**
  * 音声ファイルの整理・クリーンアップ用スクリプト。

### ⚙️ System Tools (`system-tools/`)
* **reset-folder-acl**
  * 指定フォルダのアクセス権（所有者・ACL）を強制リセットし、Administrators / SYSTEM のフルコントロールを再付与するGUI付きPowerShellスクリプト。

### 🌐 Web Tools (`web-tools/`)
* **automation_sitemaps**
  * 指定Webサイトを自動クロールしてディレクトリ階層を解析し、エクスプローラ風ツリーGUIで登録ON/OFFやPriorityの調整ができる sitemap.xml 生成ツール。
* **canonical-injector**
  * Webサイトのメンテナンスや移行時に役立つcanonicalタグの注入・管理ツール。

---

## 🚀 使い方
各ツールのディレクトリにある **`Run.bat`** をダブルクリックするか、対応するスクリプトを直接実行してください。