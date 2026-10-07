from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk


APP_NAME = "Agent QA Studio"
EXE_NAME = "AgentQAStudio.exe"


def resource_path(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / name


def ps_quote(value: str) -> str:
    return value.replace("'", "''")


def create_shortcut(shortcut: Path, target: Path, workdir: Path) -> None:
    shortcut.parent.mkdir(parents=True, exist_ok=True)
    script = (
        "$ws = New-Object -ComObject WScript.Shell; "
        f"$s = $ws.CreateShortcut('{ps_quote(str(shortcut))}'); "
        f"$s.TargetPath = '{ps_quote(str(target))}'; "
        f"$s.WorkingDirectory = '{ps_quote(str(workdir))}'; "
        f"$s.IconLocation = '{ps_quote(str(target))},0'; "
        "$s.Save()"
    )
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        check=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def install_app() -> Path:
    source = resource_path(EXE_NAME)
    if not source.exists():
        raise FileNotFoundError(f"Installer 找不到 {EXE_NAME}")

    local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    install_dir = local / "Programs" / "AgentQAStudio"
    install_dir.mkdir(parents=True, exist_ok=True)

    target = install_dir / EXE_NAME
    temp_target = install_dir / (EXE_NAME + ".new")
    shutil.copy2(source, temp_target)
    if target.exists():
        try:
            target.unlink()
        except PermissionError:
            raise RuntimeError("Agent QA Studio 目前正在執行，請先關閉後再安裝。")
    temp_target.replace(target)

    start_menu = Path(os.environ.get("APPDATA", local)) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    desktop = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop"

    create_shortcut(start_menu / f"{APP_NAME}.lnk", target, install_dir)
    try:
        create_shortcut(desktop / f"{APP_NAME}.lnk", target, install_dir)
    except Exception:
        pass

    uninstall_cmd = install_dir / "Uninstall Agent QA Studio.cmd"
    uninstall_cmd.write_text(
        "@echo off\n"
        "taskkill /IM AgentQAStudio.exe /F >nul 2>nul\n"
        "del /Q \"%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\Agent QA Studio.lnk\" >nul 2>nul\n"
        "del /Q \"%USERPROFILE%\\Desktop\\Agent QA Studio.lnk\" >nul 2>nul\n"
        "start \"\" cmd /c \"timeout /t 2 /nobreak >nul & rmdir /S /Q \\\"%LOCALAPPDATA%\\Programs\\AgentQAStudio\\\"\"\n",
        encoding="utf-8",
    )
    return target


class SetupUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Agent QA Studio Setup")
        self.geometry("520x330")
        self.resizable(False, False)

        frame = ttk.Frame(self, padding=28)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Agent QA Studio", font=("Segoe UI", 22, "bold")).pack(anchor="w")
        ttk.Label(
            frame,
            text="No-code AI Agent / LLM / RAG QA — API Auto · Browser Auto · Manual UI",
            foreground="#5d6678",
        ).pack(anchor="w", pady=(4, 20))

        ttk.Label(
            frame,
            text=(
                "將安裝到你的 Windows 使用者資料夾，不需要系統管理員權限。\n\n"
                "功能包含：API Auto、Edge/Chrome Browser Auto、Manual UI、Test Cases、"
                "Tool Calling / Arguments / RAG Sources、Edge Cases、Latency、"
                "CSV/HTML/JSON 報告與歷史紀錄。"
            ),
            wraplength=450,
            justify="left",
        ).pack(anchor="w")

        self.status = ttk.Label(frame, text="Ready", foreground="#5d6678")
        self.status.pack(anchor="w", pady=(22, 8))

        self.install_btn = ttk.Button(frame, text="安裝 Agent QA Studio", command=self.install)
        self.install_btn.pack(fill="x", ipady=7)

    def install(self):
        self.install_btn.config(state="disabled")
        self.status.config(text="Installing...")
        self.update_idletasks()
        try:
            target = install_app()
            self.status.config(text="✓ 安裝完成")
            if messagebox.askyesno("安裝完成", "Agent QA Studio 已安裝。\n\n要現在開啟嗎？"):
                subprocess.Popen([str(target)], cwd=str(target.parent))
            self.destroy()
        except Exception as exc:
            self.status.config(text="✗ 安裝失敗")
            self.install_btn.config(state="normal")
            messagebox.showerror("安裝失敗", str(exc))


if __name__ == "__main__":
    SetupUI().mainloop()
