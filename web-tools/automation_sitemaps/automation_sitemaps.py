import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import urllib.request
import urllib.parse
from html.parser import HTMLParser
from datetime import datetime
import threading

class SimpleLinkParser(HTMLParser):
    def __init__(self, base_url):
        super().__init__()
        self.base_url = base_url
        self.links = set()

    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'a':
            for attr, value in attrs:
                if attr.lower() == 'href':
                    full_url = urllib.parse.urljoin(self.base_url, value)
                    parsed = urllib.parse.urlparse(full_url)
                    clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                    
                    base_parsed = urllib.parse.urlparse(self.base_url)
                    if parsed.netloc == base_parsed.netloc:
                        self.links.add(clean_url)

class SitemapGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Mustang Sitemap Builder (Tree View)")
        self.root.geometry("900x600")

        # 上部フレーム（URL入力・スキャン）
        top_frame = ttk.Frame(root, padding=10)
        top_frame.pack(fill=tk.X)

        ttk.Label(top_frame, text="取得先URL:").pack(side=tk.LEFT, padx=5)
        self.url_entry = ttk.Entry(top_frame, width=45)
        self.url_entry.pack(side=tk.LEFT, padx=5)
        self.url_entry.insert(0, "https://example.com/")

        self.scan_btn = ttk.Button(top_frame, text="スキャン開始", command=self.start_scan)
        self.scan_btn.pack(side=tk.LEFT, padx=5)

        # 中央フレーム（ツリー表示）
        mid_frame = ttk.Frame(root, padding=10)
        mid_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("enable", "priority")
        self.tree = ttk.Treeview(mid_frame, columns=columns, selectmode="extended")
        self.tree.heading("#0", text="ディレクトリ / ページ構造", anchor="w")
        self.tree.heading("enable", text="登録", anchor="center")
        self.tree.heading("priority", text="Priority", anchor="center")
        
        self.tree.column("#0", width=550, anchor="w")
        self.tree.column("enable", width=70, anchor="center")
        self.tree.column("priority", width=90, anchor="center")
        
        tree_scroll = ttk.Scrollbar(mid_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<Double-1>", self.on_double_click)

        # 下部フレーム（操作説明 ＆ ボタン）
        bottom_frame = ttk.Frame(root, padding=10)
        bottom_frame.pack(fill=tk.X)

        info_label = ttk.Label(bottom_frame, text="💡 [登録列]ダブルクリックでON/OFF | [Priority列]ダブルクリックで数値変更", foreground="gray")
        info_label.pack(side=tk.LEFT, padx=5)

        ttk.Button(bottom_frame, text="sitemap.xml を保存", command=self.save_xml).pack(side=tk.RIGHT, padx=5)

        self.status_var = tk.StringVar(value="準備完了")
        ttk.Label(root, textvariable=self.status_var, relief=tk.SUNKEN, anchor="w").pack(fill=tk.X, padx=10, pady=5)

        self.url_to_node = {}

    def start_scan(self):
        target_url = self.url_entry.get().strip()
        if not target_url:
            messagebox.showerror("エラー", "URLを入力してください。")
            return
        
        self.scan_btn.state(["disabled"])
        self.status_var.set("スキャン中...")
        
        threading.Thread(target=self.crawl_site, args=(target_url,), daemon=True).start()

    def crawl_site(self, start_url):
        visited = set()
        to_visit = {start_url}
        found_links = set()

        try:
            while to_visit and len(visited) < 150:
                current_url = to_visit.pop()
                if current_url in visited:
                    continue
                visited.add(current_url)

                try:
                    req = urllib.request.Request(current_url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=5) as res:
                        if res.getcode() == 200 and 'text/html' in res.headers.get('Content-Type', ''):
                            html = res.read().decode('utf-8', errors='ignore')
                            parser = SimpleLinkParser(current_url)
                            parser.feed(html)
                            
                            found_links.add(current_url)
                            for link in parser.links:
                                if link not in visited:
                                    to_visit.add(link)
                except Exception:
                    pass

            self.root.after(0, lambda: self.build_tree_view(sorted(list(found_links)), start_url))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("エラー", f"スキャン中にエラーが発生しました:\n{e}"))
        finally:
            self.root.after(0, lambda: self.scan_btn.state(["!disabled"]))

    def build_tree_view(self, links, base_url):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.url_to_node.clear()

        parsed_base = urllib.parse.urlparse(base_url)
        base_prefix = f"{parsed_base.scheme}://{parsed_base.netloc}"

        # ルートノードの挿入 ("tk.END" ではなく文字列の "end" に修正)
        root_node = self.tree.insert("", "end", text=base_url, values=("[ ✓ ]", "1.0"), open=True)
        self.url_to_node[base_url] = root_node

        # ルート直下の処理
        for link in links:
            if link == base_url or link == base_url + "/":
                continue
            rel = link[len(base_prefix):].lstrip("/")
            if "/" not in rel:
                priority = "0.6"
                node = self.tree.insert(root_node, "end", text=f"📄 {rel}", values=("[ ✓ ]", priority), open=True)
                self.tree.item(node, tags=(link,))
                self.url_to_node[link] = node

        # サブディレクトリ以下の処理
        dirs_cache = {}
        for link in sorted(links):
            if link == base_url or link == base_url + "/":
                continue
            rel = link[len(base_prefix):].lstrip("/")
            if "/" in rel:
                parts = rel.split("/")
                dir_name = parts[0]
                
                if dir_name not in dirs_cache:
                    dir_node = self.tree.insert(root_node, "end", text=f"📁 {dir_name}/", values=("[ ✓ ]", "0.6"), open=True)
                    dirs_cache[dir_name] = dir_node
                
                file_name = "/".join(parts[1:])
                file_node = self.tree.insert(dirs_cache[dir_name], "end", text=f"📄 {file_name}", values=("[ ✓ ]", "0.6"), open=True)
                self.tree.item(file_node, tags=(link,))
                self.url_to_node[link] = file_node

        self.status_var.set(f"スキャン完了: {len(links)} 件のURLを検出しました（階層ツリー展開済み）")

    def on_double_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell" and region != "tree":
            return
        
        item_id = self.tree.focus()
        if not item_id:
            return

        column = self.tree.identify_column(event.x)
        vals = list(self.tree.item(item_id, "values"))
        if not vals:
            return

        if column == "#1":
            new_enable = "[   ]" if vals[0] == "[ ✓ ]" else "[ ✓ ]"
            vals[0] = new_enable
            self.tree.item(item_id, values=vals)
        elif column == "#2":
            current_pri = vals[1]
            new_pri = simpledialog.askstring("Priority 変更", f"新しいプライオリティ値を入力してください (例: 1.0, 0.8, 0.6):", initialvalue=current_pri)
            if new_pri is not None:
                vals[1] = new_pri.strip()
                self.tree.item(item_id, values=vals)

    def save_xml(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".xml", filetypes=[("XML files", "*.xml"), ("All files", "*.*")], initialfile="sitemap.xml")
        if not file_path:
            return

        today = datetime.now().strftime("%Y-%m-%d")
        xml_content = ['<?xml version="1.0" encoding="UTF-8"?>']
        xml_content.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')

        count = 0

        def collect_checked_items(node):
            nonlocal count
            vals = self.tree.item(node, "values")
            if vals and vals[0] == "[ ✓ ]":
                tags = self.tree.item(node, "tags")
                text = self.tree.item(node, "text")
                
                url = ""
                if tags:
                    url = tags[0]
                elif text.startswith("https://") or text.startswith("http://"):
                    url = text

                if url:
                    priority = vals[1]
                    xml_content.append("  <url>")
                    xml_content.append(f"    <loc>{url}</loc>")
                    xml_content.append(f"    <lastmod>{today}</lastmod>")
                    xml_content.append(f"    <changefreq>weekly</changefreq>")
                    xml_content.append(f"    <priority>{priority}</priority>")
                    xml_content.append("  </url>")
                    count += 1

            for child in self.tree.get_children(node):
                collect_checked_items(child)

        for root_child in self.tree.get_children():
            collect_checked_items(root_child)

        # ルート自体のチェック判定
        for root_node in self.tree.get_children():
            vals = self.tree.item(root_node, "values")
            text = self.tree.item(root_node, "text")
            if vals and vals[0] == "[ ✓ ]" and text.startswith("http"):
                pass

        xml_content.append("</urlset>")

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("\n".join(xml_content))
            messagebox.showinfo("成功", f"sitemap.xml を保存しました！（登録件数: {count} 件）")
            self.status_var.set(f"保存完了: {file_path}")
        except Exception as e:
            messagebox.showerror("エラー", f"保存に失敗しました:\n{e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = SitemapGUI(root)
    root.mainloop()