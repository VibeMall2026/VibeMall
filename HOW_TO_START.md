# Starting things on this PC

Every script below already changes into its own folder (`cd /d "%~dp0"`), so
**you never need to `cd` first** — double-click it in Explorer, or run it by
full path from anywhere.

---

## Trading bot

| I want | Run |
|---|---|
| The full server — watchdog, MT5 accounts, live log tail | `start_server.bat` |
| Just the bot, logs in this window | `start_bot_live.bat` |
| Stop everything | `stop_server.bat` |
| Restart | `restart_server.bat` |
| Watch the logs only | `watch_logs_live.bat` |

From a terminal:

```cmd
"C:\Users\ADMIN\VibeMall-77d8112a\start_server.bat"
```

`start_server.bat` runs `startup_manager.py`, then checks the MT5 multi-instance
accounts and starts them if none are running, then tails `logs\bot_shared.log`.
Ctrl+C stops the log tail — it does **not** stop the bot. Use `stop_server.bat`
for that.

---

## VibeMall website (local copy)

```cmd
"C:\Users\ADMIN\VibeMall-77d8112a\run_django.bat"
```

Then open <http://127.0.0.1:8000/>.

This is only a local copy for testing. The real shop runs on the VPS and is
deployed by pushing to `main` — nothing here affects it.

---

## The `cd ... ; script` trap

This fails:

```cmd
C:\Users\ADMIN> cd "C:\Users\ADMIN\VibeMall-77d8112a"; .\start_server.bat
The system cannot find the path specified.
```

`;` separates commands in **PowerShell**, not in **cmd.exe**. Command Prompt
read the whole line as one folder name — including the `; .\start_server.bat`
part — and could not find it.

| Shell | Chain two commands with |
|---|---|
| cmd.exe (`C:\...>`) | `&&` |
| PowerShell (`PS C:\...>`) | `;` |

So either of these works:

```cmd
cd /d "C:\Users\ADMIN\VibeMall-77d8112a" && start_server.bat
```

```powershell
cd "C:\Users\ADMIN\VibeMall-77d8112a"; .\start_server.bat
```

But neither is necessary — just run the script by its full path.

---

## Making it one click

1. Open `C:\Users\ADMIN\VibeMall-77d8112a` in Explorer.
2. Right-click `start_server.bat` → **Send to** → **Desktop (create shortcut)**.
3. Rename the shortcut to *Trading Bot*.

To start it automatically at login, put that shortcut in:

```
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
```

Paste that into the Explorer address bar to open the folder.

---

## If it will not start

* **`'python' is not recognized`** — Python is not on PATH. It is installed at
  `C:\Users\ADMIN\AppData\Local\Programs\Python\Python311\python.exe`;
  `start_bot_live.bat` already uses that full path and will still work.
* **The window flashes and closes** — run it from a terminal instead of
  double-clicking, so the error stays on screen:
  ```cmd
  cmd /k "C:\Users\ADMIN\VibeMall-77d8112a\start_server.bat"
  ```
* **Nothing appears in the logs** — check `logs\bot_shared.log` exists. The
  script waits for that file and will sit quietly until something writes to it.
