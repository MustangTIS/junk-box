import os
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from urllib.parse import urljoin, urlparse
import webbrowser

from bs4 import BeautifulSoup
from pyvis.network import Network
import requests


class LinkCrawlerGUI:

    def __init__(self, root):
        self.root = root
        self.root.title("Webサイト内部リンク可視化ツール (404検知機能付)")
        self.root.geometry("520x360")
        self.root.resizable(False, False)

        # 全体フレーム
        frame = ttk.Frame(root, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # 1. URL入力欄
        ttk.Label(
            frame, text="対象WebサイトのURL:", font=("", 10, "bold")
        ).pack(anchor=tk.W, pady=(0, 5))
        self.url_entry = ttk.Entry(frame, width=60)
        self.url_entry.insert(0, "https://example.com/")
        self.url_entry.pack(fill=tk.X, pady=(0, 15))

        # 2. 最大ページ数設定
        ttk.Label(frame, text="最大巡回ページ数:").pack(anchor=tk.W, pady=(0, 5))
        self.max_pages_spin = ttk.Spinbox(frame, from_=5, to=500, width=10)
        self.max_pages_spin.set(200)
        self.max_pages_spin.pack(anchor=tk.W, pady=(0, 15))

        # 3. 実行ボタン
        self.run_btn = ttk.Button(
            frame, text="解析スタート", command=self.start_crawling_thread
        )
        self.run_btn.pack(fill=tk.X, ipady=5, pady=(0, 15))

        # 4. ログ・プログレス表示
        self.progress = ttk.Progressbar(frame, mode="indeterminate")
        self.progress.pack(fill=tk.X, pady=(0, 10))

        self.status_label = ttk.Label(
            frame, text="待機中...", foreground="gray"
        )
        self.status_label.pack(anchor=tk.W)

    def start_crawling_thread(self):
        """UIがフリーズしないように別スレッドで処理を開始"""
        url = self.url_entry.get().strip()
        if not url.startswith(("http://", "https://")):
            messagebox.showerror(
                "エラー", "URLは http:// または https:// から始めてください。"
            )
            return

        # UIの操作不可処理
        self.run_btn.config(state=tk.DISABLED)
        self.progress.start(10)
        self.status_label.config(
            text="解析中... しばらくお待ちください", foreground="blue"
        )

        # スレッド起動
        thread = threading.Thread(
            target=self.run_crawler, args=(url, int(self.max_pages_spin.get()))
        )
        thread.daemon = True
        thread.start()

    def run_crawler(self, start_url, max_pages):
        """クローリング＆可視化のバックグラウンド処理"""
        target_domain = urlparse(start_url).netloc
        visited = set()
        to_visit = [start_url]
        edges = []
        error_nodes = {}  # エラーページのURLとメッセージを記録 {url: status_msg}

        try:
            while to_visit and len(visited) < max_pages:
                current_url = to_visit.pop(0).split("#")[0]
                if current_url in visited:
                    continue

                visited.add(current_url)

                # UIに進捗表示
                self.status_label.config(
                    text=f"取得中 [{len(visited)}/{max_pages}]: {urlparse(current_url).path or '/'}"
                )

                try:
                    res = requests.get(
                        current_url,
                        timeout=5,
                        headers={"User-Agent": "MyGUIContainer/1.0"},
                    )

                    # 404などのHTTPエラー検知
                    if res.status_code != 200:
                        error_nodes[current_url] = f"HTTP {res.status_code}"
                        continue

                    if "text/html" not in res.headers.get("Content-Type", ""):
                        continue

                except Exception:
                    # 接続エラーやタイムアウト
                    error_nodes[current_url] = "Connection Error"
                    continue

                soup = BeautifulSoup(res.text, "html.parser")
                for a_tag in soup.find_all("a", href=True):
                    href = a_tag["href"].strip()
                    if not href or href.startswith(
                        ("javascript:", "mailto:", "tel:", "data:")
                    ):
                        continue

                    full_url = urljoin(current_url, href).split("#")[0]
                    if urlparse(full_url).netloc == target_domain:
                        edges.append((current_url, full_url))
                        if full_url not in visited and full_url not in to_visit:
                            to_visit.append(full_url)

            # --- pyvis 描画処理 ---
            self.status_label.config(text="マップを作成中...")

            # height="100vh" でウィンドウいっぱいに全画面表示
            net = Network(
                height="100vh",
                width="100%",
                directed=True,
                bgcolor="#222222",
                font_color="white",
            )

            # JSオプションで物理演算とフォントサイズを統合設定
            net.set_options("""
            var options = {
              "configure": {
                "enabled": false
              },
              "nodes": {
                "font": {
                  "size": 12
                }
              },
              "physics": {
                "barnesHut": {
                  "gravitationalConstant": -4000,
                  "centralGravity": 0.3,
                  "springLength": 95,
                  "springConstant": 0.04,
                  "damping": 0.09
                },
                "maxVelocity": 50,
                "minVelocity": 0.75
              }
            }
            """)

            # ノードの追加（正常とエラーで色・形状を分岐）
            for url in visited:
                path = urlparse(url).path
                label_text = path if path else "/"

                if url in error_nodes:
                    err_msg = error_nodes[url]
                    net.add_node(
                        url,
                        label=f"⚠️ {label_text}",
                        title=f"{url}\n({err_msg})",
                        color="#FF5722",
                        shape="diamond",
                    )
                else:
                    net.add_node(
                        url, label=label_text, title=url, color="#2B7CE9"
                    )

            for src, dst in edges:
                if src in visited and dst in visited:
                    net.add_edge(src, dst)

            # ファイル保存処理
            output_file = "site_link_map.html"
            net.write_html(output_file)

            # 完了処理呼び出し
            self.root.after(
                0,
                self.on_complete,
                True,
                len(visited),
                len(error_nodes),
                output_file,
            )

        except Exception as e:
            self.root.after(0, self.on_complete, False, 0, str(e), "")

    def on_complete(self, success, total_pages, error_count, output_file):
        """完了後のUI復帰とブラウザ起動"""
        self.progress.stop()
        self.run_btn.config(state=tk.NORMAL)

        if success:
            status_text = f"完了！ (全{total_pages}件 / エラー{error_count}件)"
            self.status_label.config(
                text=status_text,
                foreground="red" if error_count > 0 else "green",
            )

            full_path = os.path.abspath(output_file)
            webbrowser.open(f"file://{full_path}")

            msg = f"解析が完了しました！\nブラウザでマップを開きます。\n\n解析数: {total_pages} ページ\nエラー(404等): {error_count} 箇所"
            messagebox.showinfo("完了", msg)
        else:
            self.status_label.config(
                text="エラーが発生しました", foreground="red"
            )
            messagebox.showerror(
                "エラー", f"処理中にエラーが発生しました:\n{output_file}"
            )


if __name__ == "__main__":
    root = tk.Tk()
    app = LinkCrawlerGUI(root)
    root.mainloop()