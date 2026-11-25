# Smart Process Manager (C + Python)

A Linux-focused capstone project that combines a C process-control helper with a Python/Tkinter desktop dashboard.

## Features

- Launch user-selected programs as child processes.
- Track processes launched by this application.
- Display PID, command, status, CPU usage, memory usage, nice value, and launch time.
- Pause (`SIGSTOP`), resume (`SIGCONT`), and request graceful termination (`SIGTERM`).
- Change process nice value using `setpriority()`.
- Persist the process registry between application launches and protect against PID reuse by checking process creation time.
- Uses argument arrays rather than shell execution.

## Requirements

- Linux (Ubuntu recommended; Windows users can use WSL2 with a graphical desktop/WSLg, or run under a Linux desktop).
- GCC and Make.
- Python 3.10+.
- Tkinter (`python3-tk` on Ubuntu).
- Python packages in `requirements.txt`.

## Run in VS Code (Ubuntu / WSL)

1. Open this folder in VS Code using the **WSL** extension if you are on Windows.
2. Open the integrated terminal.
3. Install system packages:

   ```bash
   sudo apt update
   sudo apt install build-essential make python3 python3-venv python3-tk -y
   ```

4. Create and activate a virtual environment:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

5. Install Python dependencies:

   ```bash
   python -m pip install -r requirements.txt
   ```

6. Compile the C helper:

   ```bash
   make
   ```

7. Launch the app:

   ```bash
   python -m python_app.app
   ```

## Using the application

- Click **Launch process** and enter a command such as `sleep 300` or `python3 demo/worker.py`.
- Select its row in the process table.
- Use **Pause**, **Resume**, **Terminate**, or **Set priority**.
- The dashboard refreshes every two seconds.
- Click **Remove finished** to clear completed process records.

Commands are parsed into an argument list; shell operators such as pipes and redirection are intentionally not supported.

## Run tests

```bash
python -m pip install pytest
make test
```

## Important safety and design notes

- Use this application on Linux. The C helper uses POSIX APIs (`kill`, `setpriority`, `getpriority`).
- The dashboard only enables operations for processes in its own registry and verifies process creation time and user ID before controlling them. This helps prevent accidental control of unrelated processes and PID-reuse mistakes.
- The C helper is a local executable and, by itself, accepts a PID. Do not expose it as a privileged service or run it with elevated privileges.
- Closing the dashboard does not terminate launched processes.
- CPU readings are sampled periodically and may show 0.0 on the first refresh.
- A process may exit between verification and the system call; the app reports system errors in that case.
- Changing a process to a more favorable nice value (a lower number) may require elevated privileges. The app intentionally does not request root access.

## Project structure

```text
smart-process-manager/
├── c_engine/
│   └── process_control.c
├── python_app/
│   ├── __init__.py
│   └── app.py
├── demo/
│   └── worker.py
├── tests/
│   └── test_process_control.py
├── Makefile
├── requirements.txt
└── README.md
```

## Capstone concepts demonstrated

`fork`/`exec` process creation concepts, process IDs, process monitoring, POSIX signals, scheduling priority (nice values), process lifecycle, parent/child relationships, Python subprocess management, and C/Python integration.
