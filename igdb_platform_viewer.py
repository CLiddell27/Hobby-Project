"""
Standalone IGDB Platform Viewer.

Shows every platform, number of games per platform, and raw JSON for the
underlying platform and count queries.

Usage:
    python igdb_platform_viewer.py
"""

import json
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
import urllib.error
import urllib.request

from igdb_client import REGION_LABELS, load_config, _get_access_token


class IGDBPlatformViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("IGDB Platform Viewer")
        self.root.geometry("1280x760")

        self._headers = None
        self._platforms = []
        self._is_busy = False
        self._last_platform_queries = []
        self._last_count_query = ""
        self._last_count_json = ""
        self._region_vars = {}

        self._build_ui()

    def _build_ui(self):
        top = ttk.Frame(self.root, padding=10)
        top.pack(side="top", fill="x")

        self.status_var = tk.StringVar(value="Ready")
        self.progress_var = tk.StringVar(value="")

        ttk.Button(top, text="1) Load Platforms", command=self.load_platforms).pack(side="left")
        ttk.Button(top, text="2) Count Games For All", command=self.count_all_platforms).pack(side="left", padx=(8, 0))
        ttk.Button(top, text="Count Selected", command=self.count_selected_platform).pack(side="left", padx=(8, 0))

        ttk.Label(top, textvariable=self.status_var).pack(side="left", padx=(18, 0))
        ttk.Label(top, textvariable=self.progress_var).pack(side="left", padx=(12, 0))

        region_frame = ttk.LabelFrame(self.root, text="Regions", padding=10)
        region_frame.pack(side="top", fill="x", padx=10, pady=(0, 10))

        ttk.Label(
            region_frame,
            text="Unchecked means all regions. Checked regions count unique games from release_dates for those regions only.",
        ).pack(side="top", anchor="w")

        checks = ttk.Frame(region_frame)
        checks.pack(side="top", fill="x", pady=(6, 0))
        for idx, region_id in enumerate(sorted(REGION_LABELS)):
            var = tk.BooleanVar(value=False)
            self._region_vars[region_id] = var
            ttk.Checkbutton(
                checks,
                text=f"{REGION_LABELS[region_id]} ({region_id})",
                variable=var,
            ).grid(row=idx // 5, column=idx % 5, sticky="w", padx=(0, 12), pady=2)

        main = ttk.Panedwindow(self.root, orient="horizontal")
        main.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        left = ttk.Frame(main)
        right = ttk.Frame(main)
        main.add(left, weight=3)
        main.add(right, weight=2)

        cols = ("platform_id", "name", "category", "game_count")
        self.tree = ttk.Treeview(left, columns=cols, show="headings")
        self.tree.heading("platform_id", text="Platform ID")
        self.tree.heading("name", text="Platform Name")
        self.tree.heading("category", text="Category")
        self.tree.heading("game_count", text="Game Count")

        self.tree.column("platform_id", width=100, anchor="center")
        self.tree.column("name", width=360, anchor="w")
        self.tree.column("category", width=100, anchor="center")
        self.tree.column("game_count", width=120, anchor="e")

        yscroll = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)

        self.tree.pack(side="left", fill="both", expand=True)
        yscroll.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._on_platform_selected)

        nb = ttk.Notebook(right)
        nb.pack(fill="both", expand=True)

        query_frame = ttk.Frame(nb, padding=8)
        raw_frame = ttk.Frame(nb, padding=8)
        nb.add(query_frame, text="Query Log")
        nb.add(raw_frame, text="Raw JSON")

        self.query_text = tk.Text(query_frame, wrap="none", height=20)
        self.query_text.pack(fill="both", expand=True)
        self.query_text.configure(state="disabled")

        self.raw_json_text = tk.Text(raw_frame, wrap="none", height=20)
        self.raw_json_text.pack(fill="both", expand=True)
        self.raw_json_text.configure(state="disabled")

    def _set_busy(self, busy, status=None):
        self._is_busy = busy
        if status is not None:
            self.status_var.set(status)

    def _set_query_log(self, text):
        self.query_text.configure(state="normal")
        self.query_text.delete("1.0", "end")
        self.query_text.insert("1.0", text)
        self.query_text.configure(state="disabled")

    def _set_raw_json(self, text):
        self.raw_json_text.configure(state="normal")
        self.raw_json_text.delete("1.0", "end")
        self.raw_json_text.insert("1.0", text)
        self.raw_json_text.configure(state="disabled")

    def _ensure_headers(self):
        cfg = load_config()
        client_id = str(cfg.get("client_id", "")).strip()
        client_secret = str(cfg.get("client_secret", "")).strip()

        if not client_id or not client_secret:
            raise RuntimeError("IGDB is not configured. Set credentials in credentials.py or saved igdb_config.json.")

        token, _ = _get_access_token(client_id, client_secret)
        return {
            "Client-ID": client_id,
            "Authorization": f"Bearer {token}",
            "Content-Type": "text/plain",
        }

    def _selected_region_ids(self):
        return [region_id for region_id, var in sorted(self._region_vars.items()) if var.get()]

    def _selected_region_label(self):
        region_ids = self._selected_region_ids()
        if not region_ids:
            return "all regions"
        return ", ".join(REGION_LABELS.get(region_id, str(region_id)) for region_id in region_ids)

    def _igdb_post(self, endpoint, query, retries=4, timeout=20):
        last_error = None
        for attempt in range(retries):
            req = urllib.request.Request(
                f"https://api.igdb.com/v4/{endpoint}",
                data=query.encode("utf-8"),
                headers=self._headers,
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    raw = resp.read().decode("utf-8", errors="replace")
                parsed = json.loads(raw)
                return parsed, raw
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code == 401 and attempt < retries - 1:
                    # Token may have expired; refresh headers once and retry.
                    self._headers = self._ensure_headers()
                    continue
                if exc.code == 429 and attempt < retries - 1:
                    retry_after = exc.headers.get("Retry-After")
                    try:
                        wait_s = float(retry_after) if retry_after else 1.0
                    except (TypeError, ValueError):
                        wait_s = 1.0
                    time.sleep(max(0.5, min(wait_s, 8.0)) + attempt * 0.5)
                    continue
                detail = exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"HTTP {exc.code} on /{endpoint}: {detail}") from exc
            except Exception as exc:
                last_error = exc
                if attempt < retries - 1:
                    time.sleep(0.5 + attempt * 0.5)
                    continue
                raise

        raise RuntimeError(f"Request failed for /{endpoint}: {last_error}")

    def load_platforms(self):
        if self._is_busy:
            return

        def worker():
            self.root.after(0, lambda: self._set_busy(True, "Loading platforms..."))
            self.root.after(0, lambda: self.progress_var.set(""))
            try:
                self._headers = self._ensure_headers()
                platforms = []
                query_log = []
                offset = 0
                page_size = 500

                while True:
                    query = f"fields id,name,category; limit {page_size}; offset {offset};"
                    page, raw = self._igdb_post("platforms", query)
                    query_log.append(
                        f"POST /platforms\n{query}\n--- RESPONSE ---\n{raw}\n\n"
                    )
                    if not page:
                        break
                    platforms.extend(page)
                    self.root.after(
                        0,
                        lambda n=len(platforms): self.progress_var.set(f"Fetched {n} platforms")
                    )
                    if len(page) < page_size:
                        break
                    offset += page_size

                platforms.sort(key=lambda p: str(p.get("name", "")).lower())
                self._platforms = platforms
                self._last_platform_queries = query_log

                self.root.after(0, self._refresh_tree)
                self.root.after(0, lambda: self._set_query_log("".join(query_log)))
                self.root.after(0, lambda: self._set_raw_json(json.dumps(platforms, indent=2)))
                self.root.after(0, lambda: self.status_var.set(f"Loaded {len(platforms)} platforms"))
            except Exception as exc:
                self.root.after(0, lambda: messagebox.showerror("IGDB Platform Viewer", str(exc)))
                self.root.after(0, lambda: self.status_var.set("Load failed"))
            finally:
                self.root.after(0, lambda: self.progress_var.set(""))
                self.root.after(0, lambda: self._set_busy(False))

        threading.Thread(target=worker, daemon=True).start()

    def _refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        for p in self._platforms:
            game_count = p.get("game_count", "")
            values = (
                p.get("id", ""),
                p.get("name", ""),
                p.get("category", ""),
                game_count,
            )
            self.tree.insert("", "end", iid=str(p.get("id")), values=values)

    def _find_platform(self, platform_id):
        for p in self._platforms:
            if p.get("id") == platform_id:
                return p
        return None

    def _count_games_for_platform(self, platform_id):
        region_ids = self._selected_region_ids()
        if not region_ids:
            query = f"where platforms = ({platform_id});"
            parsed, raw = self._igdb_post("games/count", query)

            count = None
            if isinstance(parsed, dict):
                count = parsed.get("count")
            elif isinstance(parsed, list) and parsed:
                first = parsed[0]
                if isinstance(first, dict):
                    count = first.get("count")

            if count is None:
                raise RuntimeError(f"Unexpected count response for platform {platform_id}: {raw}")

            return int(count), [f"POST /games/count\n{query}\n--- RESPONSE ---\n{raw}\n\n"], raw

        queries = []
        game_ids = set()
        last_raw = "[]"
        for region_id in region_ids:
            offset = 0
            page_size = 500
            while True:
                query = (
                    f"where platform = {platform_id} & region = {region_id}; "
                    f"fields game,region,date; "
                    f"limit {page_size}; offset {offset};"
                )
                parsed, raw = self._igdb_post("release_dates", query)
                queries.append(f"POST /release_dates\n{query}\n--- RESPONSE ---\n{raw}\n\n")
                last_raw = raw
                if not parsed:
                    break
                for row in parsed:
                    game_id = row.get("game")
                    if game_id is not None:
                        game_ids.add(game_id)
                if len(parsed) < page_size:
                    break
                offset += page_size

        summary_raw = json.dumps(
            {
                "platform_id": platform_id,
                "regions": region_ids,
                "region_labels": [REGION_LABELS.get(region_id, str(region_id)) for region_id in region_ids],
                "unique_game_count": len(game_ids),
                "unique_game_ids": sorted(game_ids),
                "last_page_raw": json.loads(last_raw),
            },
            indent=2,
        )
        return len(game_ids), queries, summary_raw

    def count_all_platforms(self):
        if self._is_busy:
            return
        if not self._platforms:
            messagebox.showinfo("IGDB Platform Viewer", "Load platforms first.")
            return

        def worker():
            region_label = self._selected_region_label()
            self.root.after(0, lambda: self._set_busy(True, f"Counting games for all platforms ({region_label})..."))
            total = len(self._platforms)
            raw_entries = []
            try:
                for idx, p in enumerate(self._platforms, start=1):
                    pid = p.get("id")
                    try:
                        count, query_entries, raw = self._count_games_for_platform(pid)
                        p["game_count"] = count
                        raw_entries.extend(query_entries)
                    except Exception as exc:
                        p["game_count"] = f"ERR: {exc}"
                    self.root.after(
                        0,
                        lambda i=idx, n=total: self.progress_var.set(f"Counted {i}/{n} platforms")
                    )
                    self.root.after(0, self._refresh_tree)

                combined_queries = "".join(self._last_platform_queries) + "\n" + "".join(raw_entries)
                self.root.after(0, lambda: self._set_query_log(combined_queries))
                self.root.after(0, lambda: self._set_raw_json(json.dumps(self._platforms, indent=2)))
                self.root.after(0, lambda: self.status_var.set(f"Finished counting all platforms ({region_label})"))
            finally:
                self.root.after(0, lambda: self.progress_var.set(""))
                self.root.after(0, lambda: self._set_busy(False))

        threading.Thread(target=worker, daemon=True).start()

    def count_selected_platform(self):
        if self._is_busy:
            return

        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("IGDB Platform Viewer", "Select a platform row first.")
            return

        platform_id = int(selected[0])

        def worker():
            region_label = self._selected_region_label()
            self.root.after(0, lambda: self._set_busy(True, f"Counting games for platform {platform_id} ({region_label})..."))
            try:
                count, query_entries, raw = self._count_games_for_platform(platform_id)
                platform = self._find_platform(platform_id)
                if platform is not None:
                    platform["game_count"] = count
                self._last_count_query = "".join(query_entries)
                self._last_count_json = raw

                self.root.after(0, self._refresh_tree)
                self.root.after(0, lambda: self._set_query_log("".join(query_entries)))
                pretty = json.dumps(json.loads(raw), indent=2)
                self.root.after(0, lambda: self._set_raw_json(pretty))
                self.root.after(0, lambda: self.status_var.set(f"Platform {platform_id} has {count} games ({region_label})"))
            except Exception as exc:
                self.root.after(0, lambda: messagebox.showerror("IGDB Platform Viewer", str(exc)))
                self.root.after(0, lambda: self.status_var.set("Count failed"))
            finally:
                self.root.after(0, lambda: self.progress_var.set(""))
                self.root.after(0, lambda: self._set_busy(False))

        threading.Thread(target=worker, daemon=True).start()

    def _on_platform_selected(self, _event):
        selected = self.tree.selection()
        if not selected:
            return
        platform_id = int(selected[0])
        platform = self._find_platform(platform_id)
        if not platform:
            return
        self._set_raw_json(json.dumps(platform, indent=2))


def main():
    root = tk.Tk()
    app = IGDBPlatformViewer(root)
    root.mainloop()


if __name__ == "__main__":
    main()
