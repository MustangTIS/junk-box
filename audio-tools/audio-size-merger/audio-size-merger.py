import os
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox


def select_root_a():
    dir_path = filedialog.askdirectory(title="ルートA（元・メイン）フォルダを選択")
    if dir_path:
        entry_a.delete(0, tk.END)
        entry_a.insert(0, dir_path)


def select_root_b():
    dir_path = filedialog.askdirectory(
        title="ルートB（重複・取り込み側）フォルダを選択"
    )
    if dir_path:
        entry_b.delete(0, tk.END)
        entry_b.insert(0, dir_path)


def run_merge():
    root_a = entry_a.get().strip()
    root_b = entry_b.get().strip()

    if not root_a or not root_b:
        messagebox.showerror(
            "エラー", "ルートAとルートBの両方のフォルダを指定してください。"
        )
        return

    if not os.path.exists(root_a) or not os.path.exists(root_b):
        messagebox.showerror(
            "エラー", "指定されたフォルダが存在しません。"
        )
        return

    if os.path.abspath(root_a) == os.path.abspath(root_b):
        messagebox.showerror(
            "エラー", "ルートAとルートBに同じフォルダは指定できません。"
        )
        return

    # 処理開始
    btn_run.config(state=tk.DISABLED)
    log_text.delete(1.0, tk.END)
    log_text.insert(
        tk.END, "=== 音楽ファイル比較・マージ処理を開始します ===\n"
    )
    root.update()

    overwrite_count = 0
    skip_count = 0
    new_count = 0
    error_count = 0

    try:
        # ルートBを基準に走査
        for root_dir, dirs, files in os.walk(root_b):
            for file in files:
                b_file_path = os.path.join(root_dir, file)
                # ルートBからの相対パス（例: ArtistA\\album\\song.flac）
                rel_path = os.path.relpath(b_file_path, root_b)
                a_file_path = os.path.join(root_a, rel_path)

                # ルートA側の対応するディレクトリが存在するか確認しつつ判定
                if os.path.exists(a_file_path):
                    try:
                        size_a = os.path.getsize(a_file_path)
                        size_b = os.path.getsize(b_file_path)

                        if size_b > size_a:
                            # ルートBの方が大きい場合は上書き
                            # 保存先フォルダが存在しない万が一の場合は作成
                            os.makedirs(
                                os.path.dirname(a_file_path), exist_ok=True
                            )
                            shutil.copy2(b_file_path, a_file_path)
                            log_text.insert(
                                tk.END,
                                f"[上書き] {rel_path}\n  (A: {size_a:,} bytes < B: {size_b:,} bytes)\n",
                            )
                            overwrite_count += 1
                        else:
                            # ルートAの方が大きい、または同じ場合はスキップ
                            log_text.insert(
                                tk.END,
                                f"[スキップ] {rel_path}\n  (Aの方が大きいか同サイズのため維持)\n",
                            )
                            skip_count += 1
                    except Exception as e:
                        log_text.insert(
                            tk.END, f"[エラー] {rel_path}: {e}\n"
                        )
                        error_count += 1
                else:
                    # ルートAに存在しないファイル（新規としてルートA側にコピーする場合）
                    # ※もし「完全に重複のみ」を対象にするならここはスキップでも良いですが、一応安全にコピーまたはスキップを選べます
                    try:
                        os.makedirs(
                            os.path.dirname(a_file_path), exist_ok=True
                        )
                        shutil.copy2(b_file_path, a_file_path)
                        log_text.insert(
                            tk.END, f"[新規コピー] {rel_path}\n"
                        )
                        new_count += 1
                    except Exception as e:
                        log_text.insert(
                            tk.END, f"[エラー(新規)] {rel_path}: {e}\n"
                        )
                        error_count += 1

                log_text.see(tk.END)
                root.update_idletasks()

        log_text.insert(
            tk.END,
            f"\n=== 処理完了 ===\n上書き: {overwrite_count}件\nスキップ: {skip_count}件\n新規追加: {new_count}件\nエラー: {error_count}件\n",
        )
        messagebox.showinfo("完了", "すべての処理が終了しました。")

    except Exception as e:
        messagebox.showerror("致命的エラー", f"予期せぬエラーが発生しました: {e}")
    finally:
        btn_run.config(state=tk.NORMAL)


# --- GUI構築 ---
root = tk.Tk()
root.title("音楽ファイル サイズ比較マージツール")
root.geometry("650x500")

# ルートA 選択フレーム
frame_a = tk.Frame(root, padx=10, pady=5)
frame_a.pack(fill=tk.X)
lbl_a = tk.Label(
    frame_a, text="ルートA（元・メイン）:", width=18, anchor="w"
)
lbl_a.pack(side=tk.LEFT)
entry_a = tk.Entry(frame_a, width=50)
entry_a.pack(side=tk.LEFT, padx=5)
btn_a = tk.Button(frame_a, text="参照...", command=select_root_a)
btn_a.pack(side=tk.LEFT)

# ルートB 選択フレーム
frame_b = tk.Frame(root, padx=10, pady=5)
frame_b.pack(fill=tk.X)
lbl_b = tk.Label(
    frame_b, text="ルートB（重複側）:", width=18, anchor="w"
)
lbl_b.pack(side=tk.LEFT)
entry_b = tk.Entry(frame_b, width=50)
entry_b.pack(side=tk.LEFT, padx=5)
btn_b = tk.Button(frame_b, text="参照...", command=select_root_b)
btn_b.pack(side=tk.LEFT)

# 実行ボタンフレーム
frame_btn = tk.Frame(root, padx=10, pady=10)
frame_btn.pack(fill=tk.X)
btn_run = tk.Button(
    frame_btn,
    text="比較して上書き統合を実行",
    bg="#d0e0ff",
    font=("Meiryo", 10, "bold"),
    command=run_merge,
)
btn_run.pack(fill=tk.X, ipady=5)

# ログ表示フレーム
frame_log = tk.Frame(root, padx=10, pady=5)
frame_log.pack(fill=tk.BOTH, expand=True)
lbl_log = tk.Label(frame_log, text="処理ログ:", anchor="w")
lbl_log.pack(fill=tk.X)

log_text = tk.Text(frame_log, wrap=tk.WORD, bg="#f5f5f5", font=("Consolas", 9))
log_text.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

scrollbar = tk.Scrollbar(frame_log, command=log_text.yview)
scrollbar.pack(fill=tk.Y, side=tk.RIGHT)
log_text.config(yscrollcommand=scrollbar.set)

root.mainloop()