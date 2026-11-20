# 🤖 Quill

**Your terminal's desk robot.** Unofficial pixel-art face for Claude Code: type `claude`, and the terminal turns into Quill, a little robot with a speech bubble, with your input box underneath.

`Python` `Textual` `Claude Code` `stream-json` `Sweetie 16`

**v0.2.0 — Stable**

---

## ✨ What it does
- 💬 **Speech-bubble chat**: Claude's replies stream into Quill's bubble as Markdown
- 🎭 **Live moods**: thinking dots, talking mouth, eyes darting while it works, a blinking red antenna when it needs you
- ✅ **Permission buttons**: Yes / Yes, don't ask again / No, or type what to do instead
- ❓ **Questions as buttons**: Claude's multiple-choice questions become clickable options
- 📜 **History**: F2 shows the whole chat so far
- 📋 **Copy anything**: drag over text + Ctrl+C, or F3 for the whole reply (works even in terminals without OSC 52, via `xclip`/`wl-copy`)
- 🔐 **Optional sudo**: approve root commands and type your password right in Quill
- 📐 **Fits small windows**: Quill shrinks to half size when space is tight
- 🔌 **Uses your own `claude`**: same login, memory, skills and settings, no extra cost

## 🚀 Install
Needs [Claude Code](https://claude.com/claude-code) installed and logged in, and Python 3.10+.
```bash
uv venv .venv && uv pip install --python .venv/bin/python -r requirements.txt
#   no uv?  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
#   (Debian/Ubuntu/Mint may need: sudo apt install python3-venv)
./install.sh            # adds the `quill` command
./install.sh --alias    # optional: `claude` opens Quill (plain Claude Code = `command claude`)
```
`--alias` edits `~/.bashrc` and `~/.zshrc`; fish users run `alias --save claude=quill`.

## 🎮 Use
| Type / press | Does |
|---|---|
| anything | talk to Claude Code |
| `quill -c` | carry on the last chat in this folder |
| `quill --resume <id>` / `--model sonnet` | any Claude Code flag passes straight through |
| `Esc` | stop Quill mid-answer |
| `F2` or `/history` | chat history |
| `/new` | fresh conversation |
| `F3` or `/copy` | copy Quill's last reply |
| drag + `Ctrl+C` | copy just the part you selected |
| `/sudo` / `/sudo off` | let Quill use sudo, or stop it |
| `Ctrl+Q` or `/quit` | leave |

## 🔐 Sudo
Off by default. `/sudo` offers **Just this chat** or **Permanently**, then either **Ask me each time** (every root command is shown and waits for your OK) or **Allow whenever** (root commands run without asking). Each choice has a second "Are you sure?" step.

- Your password lives in memory only, is typed once per Quill window, and is never written to disk.
- Claude's `sudo` is routed through a tiny shim → `sudo -A` → Quill's askpass helper → a private socket (0600). Quill only answers helpers whose parent is a real, running `sudo`.
- ⚠️ **Allow whenever** means Claude can run anything as root without showing you. Use it knowingly.

## 🛠️ How it works
Quill runs `claude -p --input-format stream-json --output-format stream-json --permission-prompt-tool stdio` behind the scenes. Claude Code's own screen is switched off; Quill reads its JSON events and draws its own screen with [Textual](https://textual.textualize.io/). Quill is drawn in the Sweetie 16 palette, using half-block characters so the pixels come out square.

## ⚠️ Known limits
- The input box is single-line: pasting multi-line text flattens it, and images aren't supported.
- Some built-in Claude Code `/commands` don't work in headless mode. Skills and custom commands pass through.
- `--resume` needs a session ID (there's no picker yet).

`preview.py` shows the four character designs that were considered (Quill is option D).

## 📄 License
MIT

*Code with rhythm. Ship with grace.*
