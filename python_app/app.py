
from __future__ import annotations

import json
import os
import shlex
import subprocess
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

try:
    import psutil
except ImportError:
    raise SystemExit("Run: python -m pip install -r requirements.txt")


ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "build" / "process_control"
REGISTRY = ROOT / "data" / "managed_processes.json"
REFRESH_MS = 2000

BG = "#0B1120"
PANEL = "#111B2E"
CARD = "#17243A"
BORDER = "#263650"
BLUE = "#3987FF"
TEXT = "#F1F5F9"
MUTED = "#91A3BB"
GREEN = "#22C55E"
RED = "#EF4444"
YELLOW = "#F59E0B"


class ProcessManagerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Smart Process Manager")
        self.root.geometry("1180x720")
        self.root.minsize(950, 600)
        self.root.configure(bg=BG)

        self.processes = {}
        self._load_registry()
        self._build_ui()
        self.refresh()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure(
            "Treeview",
            background=PANEL,
            foreground=TEXT,
            fieldbackground=PANEL,
            rowheight=39,
            borderwidth=0,
            font=("Segoe UI", 10)
        )
        style.configure(
            "Treeview.Heading",
            background=CARD,
            foreground=MUTED,
            relief="flat",
            font=("Segoe UI", 10, "bold"),
            padding=12
        )
        style.map(
            "Treeview",
            background=[("selected", "#244B83")],
            foreground=[("selected", "white")]
        )
        style.map(
            "Treeview.Heading",
            background=[("active", BORDER)]
        )

        # Header
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=30, pady=(25, 18))

        tk.Label(
            header, text="SMART PROCESS MANAGER",
            bg=BG, fg=TEXT,
            font=("Segoe UI", 22, "bold")
        ).pack(anchor="w")

        tk.Label(
            header,
            text="SYSTEM MONITORING  /  C PROCESS CONTROL ENGINE",
            bg=BG, fg=MUTED,
            font=("Segoe UI", 9, "bold")
        ).pack(anchor="w", pady=(5, 0))

        # Statistics
        stats = tk.Frame(self.root, bg=BG)
        stats.pack(fill="x", padx=30, pady=(0, 20))

        self.total_value = self._stat_card(stats, "TOTAL PROCESSES", "0", BLUE)
        self.active_value = self._stat_card(stats, "ACTIVE PROCESSES", "0", GREEN)
        self.finished_value = self._stat_card(stats, "FINISHED PROCESSES", "0", YELLOW)

        # Action panel
        actions = tk.Frame(self.root, bg=PANEL, highlightbackground=BORDER,
                           highlightthickness=1)
        actions.pack(fill="x", padx=30, pady=(0, 18))

        tk.Label(
            actions, text="PROCESS CONTROLS",
            bg=PANEL, fg=MUTED,
            font=("Segoe UI", 9, "bold")
        ).pack(side="left", padx=(16, 12), pady=14)

        buttons = [
            ("+  Launch", self.launch_process, BLUE),
            ("↻  Refresh", self.refresh, "#334155"),
            ("Ⅱ  Pause", lambda: self.send_signal("STOP"), "#334155"),
            ("▶  Resume", lambda: self.send_signal("CONT"), "#334155"),
            ("✕  Terminate", lambda: self.send_signal("TERM"), "#9F343F"),
            ("Priority", self.set_priority, "#334155"),
            ("Clear finished", self.remove_finished, "#334155")
        ]

        for label, command, color in buttons:
            self._button(actions, label, command, color).pack(
                side="left", padx=4, pady=9
            )

        # Table section
        section = tk.Frame(self.root, bg=BG)
        section.pack(fill="both", expand=True, padx=30, pady=(0, 12))

        title_row = tk.Frame(section, bg=BG)
        title_row.pack(fill="x", pady=(0, 10))

        tk.Label(
            title_row, text="Managed Processes",
            bg=BG, fg=TEXT,
            font=("Segoe UI", 15, "bold")
        ).pack(side="left")

        tk.Label(
            title_row, text="LIVE MONITORING",
            bg=BG, fg=GREEN,
            font=("Segoe UI", 9, "bold")
        ).pack(side="right")

        # Search and filter controls
        filter_row = tk.Frame(section, bg=BG)
        filter_row.pack(fill="x", pady=(0, 12))

        self.search_var = tk.StringVar()
        self.status_var = tk.StringVar(value="All")

        search_box = tk.Entry(
            filter_row,
            textvariable=self.search_var,
            bg=PANEL,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            font=("Segoe UI", 11),
            width=35
        )
        search_box.pack(side="left", ipady=10, padx=(0, 12))
        search_box.insert(0, "")
        search_box.bind("<KeyRelease>", lambda event: self.refresh())

        tk.Label(
            filter_row,
            text="STATUS:",
            bg=BG,
            fg=MUTED,
            font=("Segoe UI", 9, "bold")
        ).pack(side="left", padx=(5, 8))

        status_filter = tk.OptionMenu(
            filter_row,
            self.status_var,
            "All",
            "Running",
            "Finished",
            command=lambda value: self.refresh()
        )
        status_filter.config(
            bg=CARD,
            fg=TEXT,
            activebackground=BLUE,
            activeforeground="white",
            relief="flat",
            highlightthickness=0,
            font=("Segoe UI", 10)
        )
        status_filter["menu"].config(
            bg=CARD, fg=TEXT,
            activebackground=BLUE,
            activeforeground="white"
        )
        status_filter.pack(side="left")


        table_frame = tk.Frame(
            section, bg=PANEL,
            highlightbackground=BORDER,
            highlightthickness=1
        )
        table_frame.pack(fill="both", expand=True)

        columns = ("pid", "name", "status", "cpu", "memory", "nice", "created")
        self.tree = ttk.Treeview(
            table_frame, columns=columns,
            show="headings", selectmode="browse"
        )

        headings = {
            "pid": ("PID", 75),
            "name": ("COMMAND", 270),
            "status": ("STATUS", 120),
            "cpu": ("CPU %", 90),
            "memory": ("MEMORY MB", 110),
            "nice": ("NICE", 75),
            "created": ("STARTED", 155)
        }

        for col, (heading, width) in headings.items():
            self.tree.heading(col, text=heading)
            self.tree.column(
                col, width=width,
                anchor="w" if col == "name" else "center"
            )

        self.tree.tag_configure("running", foreground=GREEN)
        self.tree.tag_configure("finished", foreground=MUTED)
        self.tree.tag_configure("warning", foreground=YELLOW)

        scrollbar = ttk.Scrollbar(
            table_frame, orient="vertical", command=self.tree.yview
        )
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        scrollbar.pack(side="right", fill="y", pady=8, padx=(0, 5))

        # Footer
        footer = tk.Frame(self.root, bg=BG)
        footer.pack(fill="x", padx=30, pady=(0, 20))

        self.summary = tk.Label(
            footer, text="Initializing...",
            bg=BG, fg=MUTED,
            font=("Segoe UI", 9)
        )
        self.summary.pack(side="left")

        tk.Label(
            footer,
            text="SAFE MODE  •  MANAGED PROCESSES ONLY",
            bg=BG, fg="#64748B",
            font=("Segoe UI", 8, "bold")
        ).pack(side="right")

    def _stat_card(self, parent, label, value, accent):
        card = tk.Frame(
            parent, bg=CARD,
            highlightbackground=BORDER,
            highlightthickness=1
        )
        card.pack(side="left", fill="x", expand=True, padx=(0, 12))

        tk.Frame(card, bg=accent, width=4).pack(side="left", fill="y")

        content = tk.Frame(card, bg=CARD)
        content.pack(fill="both", expand=True, padx=16, pady=12)

        tk.Label(
            content, text=label,
            bg=CARD, fg=MUTED,
            font=("Segoe UI", 9, "bold")
        ).pack(anchor="w")

        number = tk.Label(
            content, text=value,
            bg=CARD, fg=TEXT,
            font=("Segoe UI", 23, "bold")
        )
        number.pack(anchor="w", pady=(3, 0))

        return number

    def _button(self, parent, label, command, color):
        return tk.Button(
            parent, text=label, command=command,
            bg=color, fg="white",
            activebackground=BLUE,
            activeforeground="white",
            relief="flat", bd=0,
            padx=11, pady=9,
            cursor="hand2",
            font=("Segoe UI", 9, "bold")
        )

    def _load_registry(self):
        REGISTRY.parent.mkdir(parents=True, exist_ok=True)
        try:
            raw = json.loads(REGISTRY.read_text(encoding="utf-8"))
            for key, value in raw.items():
                self.processes[int(key)] = value
        except (OSError, ValueError, TypeError):
            self.processes = {}

    def _save_registry(self):
        REGISTRY.parent.mkdir(parents=True, exist_ok=True)
        REGISTRY.write_text(
            json.dumps(self.processes, indent=2),
            encoding="utf-8"
        )

    def _selected_pid(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Select process", "Select a process row first.")
            return None
        return int(selection[0])

    def _is_managed_and_same_process(self, pid):
        record = self.processes.get(pid)
        if not record:
            return False, "This PID is not in the application's registry."

        try:
            proc = psutil.Process(pid)
            if abs(proc.create_time() - float(record["create_time"])) > 0.02:
                return False, "PID appears to have been reused."

            if proc.uids().real != os.getuid():
                return False, "Process owner does not match current user."

            return True, proc
        except (psutil.NoSuchProcess, psutil.AccessDenied, KeyError, ValueError):
            return False, "Process no longer exists or cannot be verified."

    def launch_process(self):
        command = simpledialog.askstring(
            "Launch process",
            "Enter a program and arguments (no shell syntax).\n"
            "Example: sleep 300\n"
            "Or: python3 demo/worker.py"
        )
        if not command:
            return

        try:
            args = shlex.split(command)
            if not args:
                return

            proc = subprocess.Popen(
                args,
                cwd=str(ROOT),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )

            time.sleep(0.05)
            ps = psutil.Process(proc.pid)

            self.processes[proc.pid] = {
                "command": command,
                "create_time": ps.create_time(),
                "launched_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }

            self._save_registry()
            self.refresh()
            messagebox.showinfo(
                "Process launched",
                f"Started successfully.\nPID: {proc.pid}"
            )

        except (OSError, psutil.Error, ValueError) as exc:
            messagebox.showerror("Launch failed", str(exc))

    def _run_engine(self, *args):
        if not ENGINE.exists():
            messagebox.showerror(
                "C engine missing",
                "Compile the C engine first using: make"
            )
            return False

        try:
            result = subprocess.run(
                [str(ENGINE), *map(str, args)],
                capture_output=True,
                text=True,
                timeout=8,
                check=False
            )

            output = (result.stdout or "") + (result.stderr or "")

            if result.returncode != 0:
                messagebox.showerror(
                    "Operation failed",
                    output.strip() or "C engine returned an error."
                )
                return False

            self.summary.config(text=output.strip())
            return True

        except (OSError, subprocess.TimeoutExpired) as exc:
            messagebox.showerror("C engine error", str(exc))
            return False

    def send_signal(self, signal_name):
        pid = self._selected_pid()
        if pid is None:
            return

        valid, result = self._is_managed_and_same_process(pid)
        if not valid:
            messagebox.showwarning("Cannot control process", result)
            return

        if signal_name == "TERM" and not messagebox.askyesno(
            "Confirm termination",
            f"Send SIGTERM to managed process {pid}?"
        ):
            return

        if self._run_engine("signal", pid, signal_name):
            self.root.after(300, self.refresh)

    def set_priority(self):
        pid = self._selected_pid()
        if pid is None:
            return

        valid, result = self._is_managed_and_same_process(pid)
        if not valid:
            messagebox.showwarning("Cannot change priority", result)
            return

        value = simpledialog.askinteger(
            "Set nice value",
            "Enter nice value (-20 to 19):",
            minvalue=-20,
            maxvalue=19
        )

        if value is not None:
            if self._run_engine("priority", pid, value):
                self.refresh()

    def remove_finished(self):
        removed = 0

        for pid in list(self.processes):
            try:
                psutil.Process(pid)
            except psutil.NoSuchProcess:
                self.processes.pop(pid, None)
                removed += 1

        self._save_registry()
        self.refresh()
        self.summary.config(
            text=f"Removed {removed} finished process record(s)."
        )

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        alive = 0
        finished = 0

        for pid, record in list(self.processes.items()):
            try:
                proc = psutil.Process(pid)

                if abs(proc.create_time() - float(record["create_time"])) > 0.02:
                    status, cpu, memory, nice = "PID reused", 0.0, 0.0, "-"
                    tag = "warning"
                else:
                    status = proc.status()
                    cpu = proc.cpu_percent(interval=None)
                    memory = proc.memory_info().rss / (1024 * 1024)
                    nice = proc.nice()
                    alive += 1
                    tag = "running"

                name = record.get("command", proc.name())[:55]

            except psutil.NoSuchProcess:
                status, cpu, memory, nice = "finished", 0.0, 0.0, "-"
                name = record.get("command", "unknown")[:55]
                tag = "finished"
                finished += 1

            except (psutil.AccessDenied, KeyError, ValueError):
                continue
                            # Apply search and status filters
            query = self.search_var.get().strip().lower()
            selected_status = self.status_var.get()

            if query and query not in str(pid).lower() and query not in name.lower():
                continue

            if selected_status == "Running" and tag != "running":
                continue

            if selected_status == "Finished" and tag != "finished":
                continue

            self.tree.insert(
                "", "end", iid=str(pid),
                values=(
                    pid, name, status,
                    f"{cpu:.1f}", f"{memory:.1f}",
                    nice, record.get("launched_at", "")
                ),
                tags=(tag,)
            )

        total = len(self.processes)
        self.total_value.config(text=str(total))
        self.active_value.config(text=str(alive))
        self.finished_value.config(text=str(finished))

        self.summary.config(
            text=f"Monitoring {total} processes  •  "
                 f"{alive} active  •  Auto-refresh every 2 seconds"
        )

        self.root.after(REFRESH_MS, self.refresh)

    def on_close(self):
        self.root.destroy()


def main():
    root = tk.Tk()
    ProcessManagerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
    