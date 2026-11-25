import tkinter as tk
from xml.sax.saxutils import escape
from tkinter import ttk, messagebox, filedialog, simpledialog
import urllib.request
import urllib.parse
from html.parser import HTMLParser
from datetime import datetime
import threading
import os

APP_VERSION = "1.3.0"


def normalize_root_url(url: str) -> str:
    """ルートURL（スキーム＋ホスト）を正規化し、末尾スラッシュを統一する。"""
    parsed = urllib.parse.urlparse(url.strip())
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc
    if not netloc and parsed.path:
        reparsed = urllib.parse.urlparse(f"https://{url.strip()}")
        scheme = reparsed.scheme
        netloc = reparsed.netloc
    return f"{scheme}://{netloc}/"


def normalize_crawled_url(base_url: str, href: str, root_url: str) -> str | None:
    """リンク先URLを正規化し、同一オリジンかつクロール対象として扱える形にする。"""
    if not href:
        return None
    href = href.strip()
    lower_href = href.lower()
    if lower_href.startswith(("javascript:", "mailto:", "tel:", "#")):
        return None

    joined = urllib.parse.urljoin(base_url, href)
    parsed = urllib.parse.urlparse(joined)

    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None

    root_parsed = urllib.parse.urlparse(root_url)
    if parsed.netloc.lower() != root_parsed.netloc.lower():
        return None

    path = parsed.path if parsed.path else "/"
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{path}"


def get_default_page_priority(file_name: str, has_subdir: bool) -> str:
    """ページ種別に応じた初期Priorityを返す（サブディレクトリのindexは0.7）。"""
    if has_subdir and file_name.lower() in ("index.html", "index.htm"):
        return "0.7"
    return "0.6"


class SimpleLinkParser(HTMLParser):
    def __init__(self, base_url: str, root_url: str):
        super().__init__()
        self.base_url = base_url
        self.root_url = root_url
        self.links = set()

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            for attr, value in attrs:
                if attr.lower() == "href":
                    clean = normalize_crawled_url(self.base_url, value, self.root_url)
                    if clean:
                        self.links.add(clean)


class SitemapGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(f"Automation Sitemap Builder v{APP_VERSION}")
        self.root.geometry("1020x650")

        self.root_url = ""
        self.url_to_node = {}
        self.node_meta = {}  # item_id -> {"kind": "root"|"dir"|"page", "url": str|None, "path": str}

        # 上部フレーム（URL入力・上限数・スキャン）
        top_frame = ttk.Frame(root, padding=10)
        top_frame.pack(fill=tk.X)

        ttk.Label(top_frame, text="取得先URL:").pack(side=tk.LEFT, padx=(0, 5))
        self.url_entry = ttk.Entry(top_frame, width=42)
        self.url_entry.pack(side=tk.LEFT, padx=5)
        self.url_entry.insert(0, "https://example.com/")

        ttk.Label(top_frame, text="上限(0=無制限):").pack(side=tk.LEFT, padx=(10, 2))
        self.limit_entry = ttk.Entry(top_frame, width=7)
        self.limit_entry.pack(side=tk.LEFT, padx=(0, 8))
        self.limit_entry.insert(0, "200")

        self.scan_btn = ttk.Button(top_frame, text="スキャン開始", command=self.start_scan)
        self.scan_btn.pack(side=tk.LEFT, padx=5)

        # 中央フレーム（ツリー表示）
        mid_frame = ttk.Frame(root, padding=(10, 0, 10, 5))
        mid_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("enable", "priority", "disallow")
        self.tree = ttk.Treeview(mid_frame, columns=columns, selectmode="extended")
        self.tree.heading("#0", text="ディレクトリ / ページ構造", anchor="w")
        self.tree.heading("enable", text="登録", anchor="center")
        self.tree.heading("priority", text="Priority", anchor="center")
        self.tree.heading("disallow", text="robots除外", anchor="center")

        self.tree.column("#0", width=580, anchor="w")
        self.tree.column("enable", width=75, anchor="center")
        self.tree.column("priority", width=90, anchor="center")
        self.tree.column("disallow", width=95, anchor="center")

        tree_scroll = ttk.Scrollbar(mid_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<Double-1>", self.on_double_click)

        # 下部フレーム（オプション・操作説明・保存ボタン）
        bottom_frame = ttk.Frame(root, padding=10)
        bottom_frame.pack(fill=tk.X)

        info_label = ttk.Label(
            bottom_frame,
            text="💡 [登録/robots除外]ダブルクリック切替 | [Priority]ダブルクリックで0.0〜1.0変更",
            foreground="gray",
        )
        info_label.pack(side=tk.LEFT, padx=(0, 10))

        self.sync_robots_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            bottom_frame,
            text="登録と連動する",
            variable=self.sync_robots_var,
        ).pack(side=tk.LEFT, padx=5)

        self.export_robots_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            bottom_frame,
            text="robots.txt も出力する",
            variable=self.export_robots_var,
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(bottom_frame, text="サイトマップを保存", command=self.save_files).pack(side=tk.RIGHT, padx=5)

        self.status_var = tk.StringVar(value="準備完了")
        ttk.Label(root, textvariable=self.status_var, relief=tk.SUNKEN, anchor="w").pack(fill=tk.X, padx=10, pady=(0, 8))

    def start_scan(self):
        raw_url = self.url_entry.get().strip()
        if not raw_url:
            messagebox.showerror("エラー", "URLを入力してください。")
            return

        try:
            max_pages = int(self.limit_entry.get().strip())
            if max_pages < 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror("エラー", "上限件数は 0 以上の整数で入力してください（0は無制限）。")
            return

        root_url = normalize_root_url(raw_url)
        self.scan_btn.state(["disabled"])
        self.status_var.set("スキャン中...")

        threading.Thread(target=self.crawl_site, args=(root_url, max_pages), daemon=True).start()

    def crawl_site(self, root_url: str, max_pages: int):
        visited = set()
        queue = [root_url]
        queued = {root_url}
        found_urls = set()

        try:
            while queue:
                if max_pages > 0 and len(visited) >= max_pages:
                    break

                current_url = queue.pop(0)
                if current_url in visited:
                    continue
                visited.add(current_url)

                if len(visited) % 10 == 0 or len(visited) == 1:
                    count_now = len(visited)
                    self.root.after(0, lambda c=count_now: self.status_var.set(f"スキャン中... ({c} ページ確認済み)"))

                try:
                    req = urllib.request.Request(
                        current_url,
                        headers={"User-Agent": f"Mozilla/5.0 (compatible; AutomationSitemapBuilder/{APP_VERSION})"},
                    )
                    with urllib.request.urlopen(req, timeout=4) as res:
                        status = getattr(res, "status", None) or res.getcode()
                        content_type = res.headers.get("Content-Type", "")
                        if status == 200 and "text/html" in content_type.lower():
                            charset = res.headers.get_content_charset() or "utf-8"
                            html = res.read().decode(charset, errors="ignore")
                            parser = SimpleLinkParser(current_url, root_url)
                            parser.feed(html)

                            found_urls.add(current_url)
                            for link in sorted(parser.links):
                                if link not in visited and link not in queued:
                                    queued.add(link)
                                    queue.append(link)
                except Exception:
                    pass

            found_urls.add(root_url)
            self.root.after(0, lambda: self.build_tree_view(sorted(found_urls), root_url))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("エラー", f"スキャン中にエラーが発生しました:\n{e}"))
        finally:
            self.root.after(0, lambda: self.scan_btn.state(["!disabled"]))

    def build_tree_view(self, urls: list[str], root_url: str):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.url_to_node.clear()
        self.node_meta.clear()

        self.root_url = root_url
        root_node = self.tree.insert("", "end", text=root_url, values=("[ ✓ ]", "1.0", "[   ]"), open=True)
        self.url_to_node[root_url] = root_node
        self.node_meta[root_node] = {"kind": "root", "url": root_url, "path": "/"}

        dirs_cache = {}

        for url in urls:
            if url == root_url:
                continue

            parsed = urllib.parse.urlparse(url)
            rel_path = parsed.path.lstrip("/")
            if not rel_path:
                continue

            is_dir_url = rel_path.endswith("/")
            trimmed = rel_path.rstrip("/")
            parts = trimmed.split("/") if trimmed else []

            if not parts:
                continue

            if is_dir_url:
                parent = root_node
                accumulated_parts = []
                for part in parts:
                    accumulated_parts.append(part)
                    key = tuple(accumulated_parts)
                    if key not in dirs_cache:
                        dir_path = "/" + "/".join(accumulated_parts) + "/"
                        d_node = self.tree.insert(
                            parent,
                            "end",
                            text=f"📁 {part}/",
                            values=("[ ✓ ]", "0.6", "[   ]"),
                            open=True,
                        )
                        dirs_cache[key] = d_node
                        self.node_meta[d_node] = {"kind": "dir", "url": None, "path": dir_path}
                    parent = dirs_cache[key]

                dir_url_node = self.tree.insert(
                    parent,
                    "end",
                    text="📄 (ディレクトリURL)",
                    values=("[ ✓ ]", "0.7", "[   ]"),
                    open=True,
                )
                self.url_to_node[url] = dir_url_node
                self.node_meta[dir_url_node] = {"kind": "page", "url": url, "path": "/" + rel_path}
            else:
                dir_parts = parts[:-1]
                file_name = parts[-1]
                parent = root_node
                accumulated_parts = []
                for part in dir_parts:
                    accumulated_parts.append(part)
                    key = tuple(accumulated_parts)
                    if key not in dirs_cache:
                        dir_path = "/" + "/".join(accumulated_parts) + "/"
                        d_node = self.tree.insert(
                            parent,
                            "end",
                            text=f"📁 {part}/",
                            values=("[ ✓ ]", "0.6", "[   ]"),
                            open=True,
                        )
                        dirs_cache[key] = d_node
                        self.node_meta[d_node] = {"kind": "dir", "url": None, "path": dir_path}
                    parent = dirs_cache[key]

                page_priority = get_default_page_priority(file_name, has_subdir=bool(dir_parts))
                page_path = "/" + "/".join(parts)
                p_node = self.tree.insert(
                    parent,
                    "end",
                    text=f"📄 {file_name}",
                    values=("[ ✓ ]", page_priority, "[   ]"),
                    open=True,
                )
                self.url_to_node[url] = p_node
                self.node_meta[p_node] = {"kind": "page", "url": url, "path": page_path}

        self.status_var.set(f"スキャン完了: {len(urls)} 件のURLを検出しました")

    def _set_descendants_state(self, node_id: str, enabled_val: str | None = None, disallow_val: str | None = None):
        """子孫ノードの状態を一括更新する。"""
        for child_id in self.tree.get_children(node_id):
            c_vals = list(self.tree.item(child_id, "values"))
            if len(c_vals) >= 3:
                if enabled_val is not None:
                    c_vals[0] = enabled_val
                if disallow_val is not None:
                    c_vals[2] = disallow_val
                self.tree.item(child_id, values=c_vals)
            self._set_descendants_state(child_id, enabled_val=enabled_val, disallow_val=disallow_val)

    def on_double_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region not in ("cell", "tree"):
            return

        item_id = self.tree.focus()
        if not item_id:
            return

        column = self.tree.identify_column(event.x)
        vals = list(self.tree.item(item_id, "values"))
        if len(vals) < 3:
            return

        meta = self.node_meta.get(item_id, {})
        sync_enabled = self.sync_robots_var.get()

        if column == "#1":
            # 登録 ON/OFF
            new_enabled = "[   ]" if vals[0] == "[ ✓ ]" else "[ ✓ ]"
            vals[0] = new_enabled
            if sync_enabled and new_enabled == "[ ✓ ]":
                vals[2] = "[   ]"
            self.tree.item(item_id, values=vals)
            if meta.get("kind") == "dir" and sync_enabled and new_enabled == "[ ✓ ]":
                self._set_descendants_state(item_id, enabled_val="[ ✓ ]", disallow_val="[   ]")
        elif column == "#2":
            # Priority 変更
            current_pri = vals[1]
            new_pri = simpledialog.askstring(
                "Priority 変更",
                "新しいプライオリティ値を入力してください (0.0 〜 1.0, 例: 1.0, 0.8, 0.6):",
                initialvalue=current_pri,
            )
            if new_pri is not None:
                try:
                    val_f = float(new_pri.strip())
                    if not (0.0 <= val_f <= 1.0):
                        messagebox.showwarning("入力範囲", "Priority は 0.0 から 1.0 の間で指定してください。")
                        return
                    vals[1] = f"{val_f:.1f}"
                    self.tree.item(item_id, values=vals)
                except ValueError:
                    messagebox.showwarning("入力エラー", "数値（例: 0.8）を入力してください。")
        elif column == "#3":
            # robots.txt 除外 (Disallow) ON/OFF
            new_disallow = "[   ]" if vals[2] == "[ ✓ ]" else "[ ✓ ]"
            vals[2] = new_disallow
            if sync_enabled and new_disallow == "[ ✓ ]":
                vals[0] = "[   ]"
            self.tree.item(item_id, values=vals)
            if meta.get("kind") == "dir" and sync_enabled and new_disallow == "[ ✓ ]":
                self._set_descendants_state(item_id, enabled_val="[   ]", disallow_val="[ ✓ ]")

    @staticmethod
    def _format_priority(raw_val: str, default: str = "0.6") -> str:
        try:
            val = float(raw_val)
            if 0.0 <= val <= 1.0:
                return f"{val:.1f}"
        except (ValueError, TypeError):
            pass
        return default

    def _build_sitemap_url_from_save_path(self, xml_path: str) -> str:
        """保存したXMLファイル名／パスからサイトマップのURLを組み立てる。"""
        base = self.root_url if self.root_url else normalize_root_url(self.url_entry.get())
        base_parsed = urllib.parse.urlparse(base)
        site_origin = f"{base_parsed.scheme}://{base_parsed.netloc}"
        filename = os.path.basename(xml_path)
        return f"{site_origin}/{filename}"

    def save_files(self):
        xml_path = filedialog.asksaveasfilename(
            defaultextension=".xml",
            filetypes=[("XML files", "*.xml"), ("All files", "*.*")],
            initialfile="sitemap.xml",
        )
        if not xml_path:
            return

        today = datetime.now().strftime("%Y-%m-%d")
        xml_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        ]

        seen_urls = set()
        sitemap_count = 0
        disallow_paths = []
        seen_disallow = set()

        def walk_node(node_id):
            nonlocal sitemap_count
            vals = self.tree.item(node_id, "values")
            meta = self.node_meta.get(node_id, {})

            enabled = bool(vals and len(vals) >= 1 and vals[0] == "[ ✓ ]")
            disallowed = bool(vals and len(vals) >= 3 and vals[2] == "[ ✓ ]")
            pri_str = (
                self._format_priority(vals[1], "1.0" if meta.get("kind") == "root" else "0.6")
                if vals and len(vals) >= 2
                else "0.6"
            )

            if disallowed:
                d_path = meta.get("path")
                if d_path and d_path not in seen_disallow:
                    seen_disallow.add(d_path)
                    disallow_paths.append(d_path)

            url = meta.get("url")
            if enabled and url and url not in seen_urls:
                seen_urls.add(url)
                xml_lines.append("  <url>")
                xml_lines.append(f"    <loc>{escape(url)}</loc>")
                xml_lines.append(f"    <lastmod>{today}</lastmod>")
                xml_lines.append(f"    <priority>{pri_str}</priority>")
                xml_lines.append("  </url>")
                sitemap_count += 1

            for child_id in self.tree.get_children(node_id):
                walk_node(child_id)

        for top_id in self.tree.get_children():
            walk_node(top_id)

        xml_lines.append("</urlset>")

        try:
            with open(xml_path, "w", encoding="utf-8") as f:
                f.write("\n".join(xml_lines) + "\n")

            robots_msg = ""
            if self.export_robots_var.get():
                default_dir = os.path.dirname(xml_path)
                robots_path = filedialog.asksaveasfilename(
                    initialdir=default_dir,
                    initialfile="robots.txt",
                    filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                )
                if robots_path:
                    sitemap_loc = self._build_sitemap_url_from_save_path(xml_path)
                    robots_lines = [
                        "User-agent: *",
                        "Allow: /",
                    ]
                    for d_path in disallow_paths:
                        robots_lines.append(f"Disallow: {d_path}")
                    robots_lines.append("")
                    robots_lines.append(f"Sitemap: {sitemap_loc}")

                    with open(robots_path, "w", encoding="utf-8") as rf:
                        rf.write("\n".join(robots_lines) + "\n")
                    robots_msg = f"\nrobots.txt: {robots_path} （Disallow {len(disallow_paths)} 件）"

            messagebox.showinfo(
                "保存完了",
                f"サイトマップを保存しました！（登録件数: {sitemap_count} 件）\n{xml_path}{robots_msg}",
            )
            self.status_var.set(f"保存完了: {xml_path} ({sitemap_count} 件)")
        except Exception as e:
            messagebox.showerror("エラー", f"保存に失敗しました:\n{e}")


if __name__ == "__main__":
    root = tk.Tk()
    app = SitemapGUI(root)
    root.mainloop()