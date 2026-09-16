import os
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox


def select_target_dir():
    dir_path = filedialog.askdirectory(title="整理対象のルートフォルダを選択")
    if dir_path:
        entry_dir.delete(0, tk.END)
        entry_dir.insert(0, dir_path)


def run_cleanup():
    target_root = entry_dir.get().strip()
    is_delete = var_mode.get()  # Trueなら完全削除、Falseなら退避

    if not target_root:
        messagebox.showerror(
            "エラー", "対象のルートフォルダを指定してください。"
        )
        return

    if not os.path.exists(target_root):
        messagebox.showerror(
            "エラー", "指定されたフォルダが存在しません。"
        )
        return

    # 確認メッセージ
    mode_str = (
        "【完全削除】" if is_delete else "【別フォルダへ退避（安全）】"
    )
    if not messagebox.askyesno(
        "確認",
        f"以下のモードで重複MP3の整理を開始します。\n\nモード: {mode_str}\n対象: {target_root}\n\nよろしいですか？",
    ):
        return

    # 処理開始
    btn_run.config(state=tk.DISABLED)
    log_text.delete(1.0, tk.END)
    log_text.insert(
        tk.END, "=== FLAC優先 MP3クリーンアップ処理を開始します ===\n"
    )
    root.update()

    removed_count = 0
    error_count = 0

    # 退避先フォルダの準備（退避モードの場合）
    backup_root = os.path.join(target_root, "_Removed_MP3_Backup")

    try:
        for root_dir, dirs, files in os.walk(target_root):
            # バックアップフォルダ自体は走査対象から除外
            if "_Removed_MP3_Backup" in root_dir:
                continue

            # 拡張子を除いたファイル名ごとに、持っている拡張子をまとめる辞書
            # 例: {"リテラチュア": [".flac", ".mp3"]}
            file_map = {}
            for file in files:
                base, ext = os.path.splitext(file)
                file_map.setdefault(base, []).append(ext.lower())

            # 各ファイルをチェック
            for base, exts in file_map.items():
                if ".flac" in exts and ".mp3" in exts:
                    flac_name = base + ".flac"
                    mp3_name = base + ".mp3"
                    mp3_path = os.path.join(root_dir, mp3_name)
                    rel_path = os.path.relpath(mp3_path, target_root)

                    try:
                        if is_delete:
                            # 完全削除
                            os.remove(mp3_path)
                            log_text.insert(
                                tk.END,
                                f"[削除] {rel_path} (同名FLACが存在するため)\n",
                            )
                        else:
                            # 退避（元のフォルダ階層を維持してバックアップフォルダへ移動）
                            rel_dir = os.path.relpath(root_dir, target_root)
                            dest_dir = (
                                backup_root
                                if rel_dir == "."
                                else os.path.join(backup_root, rel_dir)
                            )
                            os.makedirs(dest_dir, exist_ok=True)
                            dest_path = os.path.join(dest_dir, mp3_name)

                            shutil.move(mp3_path, dest_path)
                            log_text.insert(
                                tk.END,
                                f"[退避] {rel_path} -> _Removed_MP3_Backup へ移動\n",
                            )

                        removed_count += 1
                    except Exception as e:
                        log_text.insert(
                            tk.END, f"[エラー] {rel_path}: {e}\n"
                        )
                        error_count += 1

                    log_text.see(tk.END)
                    root.update_idletasks()

        log_text.insert(
            tk.END,
            f"\n=== 処理完了 ===\n対象MP3処理数: {removed_count}件\nエラー: {error_count}件\n",
        )
        messagebox.showinfo("完了", "すべての処理が終了しました。")

    except Exception as e:
        messagebox.showerror("致命的エラー", f"予期せぬエラーが発生しました: {e}")
    finally:
        btn_run.config(state=tk.NORMAL)


# --- GUI構築 ---
root = tk.Tk()
root.title("同名FLAC優先 MP3クリーナー")
root.geometry("650x450")

# フォルダ選択フレーム
frame_dir = tk.Frame(root, padx=10, pady=10)
frame_dir.pack(fill=tk.X)
lbl_dir = tk.Label(frame_dir, text="対象ルートフォルダ:", width=16, anchor="w")
lbl_dir.pack(side=tk.LEFT)
entry_dir = tk.Entry(frame_dir, width=48)
entry_dir.pack(side=tk.LEFT, padx=5)
btn_dir = tk.Button(frame_dir, text="参照...", command=select_target_dir)
btn_dir.pack(side=tk.LEFT)

# モード選択フレーム（ラジオボタン）
frame_mode = tk.Frame(root, padx=10, pady=5)
frame_mode.pack(fill=tk.X)
var_mode = tk.BooleanVar(value=False)  # 初期値は安全な退避モード
rad_backup = tk.Radiobutton(
    frame_mode,
    text="安全モード: 別フォルダ（_Removed_MP3_Backup）へ退避する",
    variable=var_mode,
    value=False,
)
rad_backup.pack(anchor="w")
rad_delete = tk.Radiobutton(
    frame_mode,
    text="完全削除モード: 同名FLACがあるMP3を直接削除する",
    variable=var_mode,
    value=True,
    fg="red",
)
rad_delete.pack(anchor="w")

# 実行ボタンフレーム
frame_btn = tk.Frame(root, padx=10, pady=10)
frame_btn.pack(fill=tk.X)
btn_run = tk.Button(
    frame_btn,
    text="FLACがある重複MP3の整理を実行",
    bg="#ffe0e0",
    font=("Meiryo", 10, "bold"),
    command=run_cleanup,
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