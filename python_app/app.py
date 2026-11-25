from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

try:
    import psutil
except ImportError:
    raise SystemExit("Missing dependency. Run: python -m pip install -r requirements.txt")

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "build" / "process_control"
REGISTRY = ROOT / "data" / "managed_processes.json"
REFRESH_MS = 2000


class ProcessManagerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Smart Process Manager")
        self.root.geometry("1050x620")
        self.root.minsize(850, 480)
        self.processes: dict[int, dict] = {}
        self._load_registry()
        self._build_ui()
        self.refresh()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_ui(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        header = ttk.Frame(self.root, padding=(16, 14))
        header.pack(fill="x")
        ttk.Label(header, text="SMART PROCESS MANAGER", font=("Segoe UI", 19, "bold")).pack(anchor="w")
        ttk.Label(header, text="C process-control engine  •  Python monitoring dashboard",
                  foreground="#64748b").pack(anchor="w", pady=(3, 0))

        toolbar = ttk.Frame(self.root, padding=(12, 4))
        toolbar.pack(fill="x")
        actions = [
            ("Launch process", self.launch_process),
            ("Refresh", self.refresh),
            ("Pause", lambda: self.send_signal("STOP")),
            ("Resume", lambda: self.send_signal("CONT")),
            ("Terminate", lambda: self.send_signal("TERM")),
            ("Set priority", self.set_priority),
            ("Remove finished", self.remove_finished),
        ]
        for label, command in actions:
            ttk.Button(toolbar, text=label, command=command).pack(side="left", padx=3, pady=4)

        columns = ("pid", "name", "status", "cpu", "memory", "nice", "created")
        self.tree = ttk.Treeview(self.root, columns=columns, show="headings", selectmode="browse")
        headings = {
            "pid": ("PID", 75), "name": ("Command", 240), "status": ("Status", 110),
            "cpu": ("CPU %", 85), "memory": ("Memory MB", 105),
            "nice": ("Nice", 65), "created": ("Started", 150)
        }
        for col, (title, width) in headings.items():
            self.tree.heading(col, text=title)
            self.tree.column(col, width=width, anchor="center" if col != "name" else "w")
        self.tree.pack(fill="both", expand=True, padx=14, pady=(8, 4))

        bottom = ttk.Frame(self.root, padding=(14, 8))
        bottom.pack(fill="x")
        self.summary = ttk.Label(bottom, text="Ready")
        self.summary.pack(side="left")
        ttk.Label(bottom, text="Select a row before using process actions.",
                  foreground="#64748b").pack(side="right")

        help_text = ("Safety: this app only offers actions for processes launched and recorded by this app. "
                     "Use harmless test commands; do not manage critical system processes.")
        ttk.Label(self.root, text=help_text, wraplength=1000, foreground="#92400e",
                  padding=(14, 4)).pack(fill="x")

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
        REGISTRY.write_text(json.dumps(self.processes, indent=2), encoding="utf-8")

    def _selected_pid(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Select process", "Select a process row first.")
            return None
        return int(selection[0])

    def _is_managed_and_same_process(self, pid: int):
        record = self.processes.get(pid)
        if not record:
            return False, "This PID is not in this application's registry."
        try:
            proc = psutil.Process(pid)
            # Protect against PID reuse: compare process creation timestamp.
            if abs(proc.create_time() - float(record["create_time"])) > 0.02:
                return False, "PID appears to have been reused; refusing to control it."
            if proc.uids().real != os.getuid():
                return False, "Process owner does not match the current user."
            return True, proc
        except (psutil.NoSuchProcess, psutil.AccessDenied, KeyError, ValueError):
            return False, "Process no longer exists or cannot be verified."

    def launch_process(self):
        command = simpledialog.askstring(
            "Launch process",
            "Enter a program and arguments (no shell syntax).\nExample: sleep 300\nOr: python3 demo/worker.py"
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
            # Give /proc a moment to become visible, then capture creation time.
            time.sleep(0.05)
            ps = psutil.Process(proc.pid)
            self.processes[proc.pid] = {
                "command": command,
                "create_time": ps.create_time(),
                "launched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            self._save_registry()
            self.refresh()
            messagebox.showinfo("Process launched", f"Started successfully.\nPID: {proc.pid}")
        except (OSError, psutil.Error, ValueError) as exc:
            messagebox.showerror("Launch failed", str(exc))

    def _run_engine(self, *args):
        if not ENGINE.exists():
            messagebox.showerror("C engine missing", "Compile the C engine first using: make")
            return False
        try:
            result = subprocess.run(
                [str(ENGINE), *map(str, args)],
                capture_output=True, text=True, timeout=8, check=False
            )
            output = (result.stdout or "") + (result.stderr or "")
            if result.returncode != 0:
                messagebox.showerror("Operation failed", output.strip() or "C engine returned an error.")
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
            "Confirm termination", f"Send SIGTERM to managed process {pid}?"
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
            "Set nice value", "Enter nice value (-20 to 19):",
            minvalue=-20, maxvalue=19
        )
        if value is not None:
            self._run_engine("priority", pid, value)
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
        self.summary.config(text=f"Removed {removed} finished process record(s).")

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        alive = 0
        for pid, record in list(self.processes.items()):
            try:
                proc = psutil.Process(pid)
                if abs(proc.create_time() - float(record["create_time"])) > 0.02:
                    status, cpu, memory, nice = "PID reused", 0.0, 0.0, "-"
                else:
                    status = proc.status()
                    cpu = proc.cpu_percent(interval=None)
                    memory = proc.memory_info().rss / (1024 * 1024)
                    nice = proc.nice()
                    alive += 1
                name = record.get("command", proc.name())[:42]
                self.tree.insert("", "end", iid=str(pid), values=(
                    pid, name, status, f"{cpu:.1f}", f"{memory:.1f}", nice,
                    record.get("launched_at", "")
                ))
            except psutil.NoSuchProcess:
                self.tree.insert("", "end", iid=str(pid), values=(
                    pid, record.get("command", "unknown"), "finished", "0.0", "0.0", "-", 
                    record.get("launched_at", "")
                ))
            except (psutil.AccessDenied, KeyError, ValueError):
                continue

        self.summary.config(text=f"Tracked: {len(self.processes)}  •  Active: {alive}  •  Auto-refresh: 2 seconds")
        self.root.after(REFRESH_MS, self.refresh)

    def on_close(self):
        # Do not kill user processes when closing the dashboard.
        self.root.destroy()


def main():
    root = tk.Tk()
    ProcessManagerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
