import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import threading

def process_html_files(directory, base_url, log_callback):
    target_dir = os.path.abspath(directory)
    updated_count = 0
    
    if not os.path.exists(target_dir):
        log_callback(f"エラー: 指定されたディレクトリが存在しません -> {target_dir}\n")
        return

    for root, dirs, files in os.walk(target_dir):
        for file in files:
            if file.lower().endswith(".html"):
                file_path = os.path.join(root, file)
                
                # フォルダ内での相対パスを計算してURLパスを生成
                rel_path = os.path.relpath(file_path, target_dir)
                url_path = rel_path.replace("\\", "/")
                
                # 先頭の不要な記号を整理
                if url_path.startswith("./"):
                    url_path = url_path[2:]
                
                canonical_url = f"{base_url.rstrip('/')}/{url_path}"
                canonical_tag = f'<link rel="canonical" href="{canonical_url}">'
                
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                except Exception as e:
                    log_callback(f"読み込みエラー: {file_path} -> {e}\n")
                    continue
                
                # 既にcanonicalタグが存在するかチェックして置換、なければ</head>の直前に追加
                if re.search(r'<link\s+rel=["\']canonical["\'][^>]*>', content, re.IGNORECASE):
                    new_content = re.sub(
                        r'<link\s+rel=["\']canonical["\'][^>]*>',
                        canonical_tag,
                        content,
                        flags=re.IGNORECASE
                    )
                elif "</head>" in content:
                    new_content = content.replace("</head>", f"    {canonical_tag}\n</head>", 1)
                elif "</HEAD>" in content:
                    new_content = content.replace("</HEAD>", f"    {canonical_tag}\n</HEAD>", 1)
                else:
                    log_callback(f"スキップ（</head>が見つかりません）: {file_path}\n")
                    continue
                
                # 変更があった場合のみファイルを上書き保存
                if new_content != content:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(new_content)
                    log_callback(f"更新完了: {url_path} -> {canonical_url}\n")
                    updated_count += 1

    log_callback(f"\n処理が完了しました。合計 {updated_count} 個のファイルを更新しました。\n")

class CanonicalApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Canonicalタグ自動挿入ツール")
        self.root.geometry("600x520")
        
        # ターゲットフォルダ選択フレーム
        dir_frame = tk.LabelFrame(root, text=" ターゲットフォルダ ", padx=10, pady=10)
        dir_frame.pack(fill="x", padx=10, pady=10)
        
        self.dir_entry = tk.Entry(dir_frame)
        self.dir_entry.pack(side="left", padx=(0, 10), expand=True, fill="x")
        
        dir_btn = tk.Button(dir_frame, text="参照...", command=self.select_directory)
        dir_btn.pack(side="right")
        
        # ベースURL入力フレーム
        url_frame = tk.LabelFrame(root, text=" ベースURL ", padx=10, pady=10)
        url_frame.pack(fill="x", padx=10, pady=10)
        
        self.url_entry = tk.Entry(url_frame)
        self.url_entry.pack(fill="x", expand=True)
        self.url_entry.insert(0, "https://example.com")
        
        # 実行ボタン
        self.exec_btn = tk.Button(root, text="実行する", bg="#4CAF50", fg="white", font=("", 11, "bold"), command=self.start_process)
        self.exec_btn.pack(fill="x", padx=10, pady=5)
        
        # 実行ログ表示エリア
        log_frame = tk.LabelFrame(root, text=" 実行ログ ", padx=10, pady=10)
        log_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.log_area = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=10)
        self.log_area.pack(fill="both", expand=True)

    def select_directory(self):
        dir_path = filedialog.askdirectory()
        if dir_path:
            self.dir_entry.delete(0, tk.END)
            self.dir_entry.insert(0, dir_path)

    def log_message(self, message):
        self.log_area.insert(tk.END, message)
        self.log_area.see(tk.END)

    def start_process(self):
        target_dir = self.dir_entry.get().strip()
        base_url = self.url_entry.get().strip()
        
        if not target_dir:
            messagebox.showerror("エラー", "ターゲットフォルダを選択してください。")
            return
        if not base_url:
            messagebox.showerror("エラー", "ベースURLを入力してください。")
            return
            
        self.log_area.delete("1.0", tk.END)
        self.exec_btn.config(state="disabled")
        
        # 別スレッドで処理を実行し、画面のフリーズを防止
        def run():
            process_html_files(target_dir, base_url, self.log_message)
            self.exec_btn.config(state="normal")
            messagebox.showinfo("完了", "処理が完了しました！")
            
        threading.Thread(target=run, daemon=True).start()

if __name__ == "__main__":
    root = tk.Tk()
    app = CanonicalApp(root)
    root.mainloop()