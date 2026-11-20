# 🤖 Quill

**Your terminal's desk robot.** Unofficial pixel-art face for Claude Code: type `quill`, and the terminal turns into **Quill** (or **Plume**), a little robot with a speech bubble, with your input box underneath.

> Unofficial fan project. Not made by or affiliated with Anthropic. You need your own [Claude Code](https://claude.com/claude-code) install and login; Quill is just a new face for it.

`Python` `Textual` `Claude Code` `stream-json` `Sweetie 16`

**v0.4.0 — In testing**

---

## ✨ What it does
- 🤖 **Quill or Plume**: pick your desk robot on first start (Plume has a feather instead of an antenna); switch any time with `/character`
- 👋 **Knows your name**: on first start your character asks what to call you, suggesting the name Claude already knows from your instructions (if any); change it with `/name`
- 🎨 **Colour schemes**: `classic` (Sweetie 16 blues) or `aurora` (Tokyo Night purples), remembered per character with `/theme`
- 🔔 **Desktop pop-ups** when Quill needs you or finishes a long job while you're in another window
- 📱 **Remote Control**: `/rc` carries the same chat on to the Claude app or claude.ai
- 💬 **Speech-bubble chat**: Claude's replies stream into Quill's bubble as Markdown
- 🗂️ **Pick up where you left off**: Quill's greeting lists your recent projects with the **next item on each roadmap**; continue the last chat or start fresh (the next item is put in your message box)
- 📝 **Multi-line input**: the message box wraps and grows; paste multi-line text freely
- 🎭 **Live moods**: thinking dots, talking mouth, eyes darting while it works, a blinking red antenna when it needs you
- ✅ **Permission buttons**: Yes / Yes, don't ask again / No, or type what to do instead
- ❓ **Questions as buttons**: Claude's multiple-choice questions become clickable options
- 📜 **History**: F2 shows the whole chat so far
- 📋 **Copy anything**: drag over text + Ctrl+C, or F3 for the whole reply (works even in terminals without OSC 52, via `xclip`/`wl-copy`)
- 🔐 **Optional sudo**: approve root commands and type your password right in Quill
- 📐 **Fits small windows**: Quill shrinks to half size when space is tight
- 🔌 **Uses your own `claude`**: same login, memory, skills and settings, no extra cost
- 🧪 **Throwaway test repos**: ask for a "test repo" and Claude keeps it local, notes what you find, and at "wrap up" summarizes it and deletes it

## 🚀 Install
Needs Linux, [Claude Code](https://claude.com/claude-code) installed and logged in, and Python 3.10+. Optional: `notify-send` (pop-ups) and `xclip` or `wl-copy` (copying in terminals without OSC 52).
```bash
uv venv .venv && uv pip install --python .venv/bin/python -r requirements.txt
#   no uv?  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
#   (Debian/Ubuntu/Mint may need: sudo apt install python3-venv)
./install.sh            # adds the `quill` and `plume` commands
./install.sh --alias    # optional: `claude` opens Quill (plain Claude Code = `command claude`)
```
`--alias` edits `~/.bashrc` and `~/.zshrc`; fish users run `alias --save claude=quill`.

## 🎮 Use
Type `quill` (or `plume`) in any terminal, from any folder; each command opens its own character (`claude` stays plain Claude Code). Pick a project from the greeting, and Quill moves there.

The "next" item comes from the project's `ROADMAP.md`, `docs/roadmap.md` or `HANDOFF.md` (a *Next* section, else the first unticked `- [ ]`, else a "Next step is…" line, else the first numbered step not marked done), skipping lines that are crossed out, dated, or optional. If there's no sensible item, or the roadmap is a week older than the last chat, Quill shows where Claude left off instead. Chats started in a folder of projects (like `GitHub Projects`) are filed under the project they worked in.

## 🛡️ Permissions
Quill runs Claude Code in **auto mode**, like a normal session: routine actions (reading, searching, Monitor, edits in the folder) don't ask. When something does ask, **Yes, and don't ask again** covers that level and everything below it until the chat ends. Levels: reading → editing files in this folder → editing files anywhere → running commands → sudo. Nothing is saved; a new chat, `/new`, `/resume` or a project switch asks again. Set `"permission_mode": "default"` in `~/.config/quill/config.json` to be asked about everything.

| Type / press | Does |
|---|---|
| anything | talk to Claude Code |
| `\` then `Enter`, or `Ctrl+J` | new line in your message (Shift+Enter too, if your terminal sends it differently from Enter; check with `quill --keys`) |
| `/resume` | pick a project to pick up again |
| `quill -c` | carry on the last chat in this folder |
| `quill --resume <id>` / `--model sonnet` | any Claude Code flag passes straight through |
| `Esc` | stop Quill mid-answer |
| `F2` or `/history` | chat history |
| `/new` | fresh conversation |
| `F3` or `/copy` | copy Quill's last reply |
| drag + `Ctrl+C` | copy just the part you selected |
| `/sudo` / `/sudo off` | let Quill use sudo, or stop it |
| `/exit` or `Ctrl+Q` | leave and close the terminal window |
| `/terminal` | leave Quill, keep the terminal open |
| `/character [quill\|plume]` | switch characters |
| `/name [your name]` | what your character calls you |
| `/theme [classic\|aurora]` | change the current character's colours |
| `/rc` / `/rc off` | Remote Control on/off |
| `/notify on\|off` | desktop pop-ups |

## 🔐 Sudo
Off by default. `/sudo` offers **Just this chat** or **Permanently**, then either **Ask me each time** (every root command is shown and waits for your OK) or **Allow whenever** (root commands run without asking). Each choice has a second "Are you sure?" step.

- Your password lives in memory only, is typed once per Quill window, and is never written to disk.
- Claude's `sudo` is routed through a tiny shim → `sudo -A` → Quill's askpass helper → a private socket (0600). Quill only answers helpers whose parent is a real, running `sudo`.
- ⚠️ **Allow whenever** means Claude can run anything as root without showing you. Use it knowingly.

## ⚙️ Settings
Everything lives in `~/.config/quill/config.json` (created as you go):

| Key | What it does |
|---|---|
| `character` | `quill` or `plume` (the `quill`/`plume` commands override it) |
| `user_name` | what your character calls you (`/name`) |
| `themes` | colour scheme per character, e.g. `{"quill": "classic", "plume": "aurora"}` |
| `notifications` | desktop pop-ups on/off (`/notify`) |
| `permission_mode` | Claude Code permission mode, default `auto` |
| `sudo` | permanent sudo setting (`/sudo`); your password is never stored |
| `shell_wrappers` | programs that run a shell inside your terminal (e.g. a terminal-effects wrapper), so `/exit` can still close the window |

## 🔒 Privacy
Quill runs entirely on your machine. To build the project list it reads Claude Code's local chat history (`~/.claude/projects`) and your projects' roadmap files; nothing is uploaded by Quill itself. Your messages go to Claude through your own Claude Code, as usual. On first start, Quill asks Claude one short, unsaved question ("do you know the user's name?") so it can suggest your name.

## 🛠️ How it works
Quill runs `claude -p --input-format stream-json --output-format stream-json --permission-prompt-tool stdio` behind the scenes. Claude Code's own screen is switched off; Quill reads its JSON events and draws its own screen with [Textual](https://textual.textualize.io/). Quill is drawn in the Sweetie 16 palette, using half-block characters so the pixels come out square.

## ⚠️ Known limits
- Images can't be pasted into the message box.
- Many terminals send Shift+Enter as plain Enter; use `\` then Enter, or Ctrl+J, there.
- Linux only for now (sudo support, window closing and pop-ups rely on Linux tools).
- Some built-in Claude Code `/commands` don't work in headless mode. Skills and custom commands pass through.

`preview.py` shows the four character designs that were considered (Quill is option D); `docs/plume_preview.py` shows the Plume mock-ups (Plume is option B).

## 📄 License
MIT

*Code with rhythm. Ship with grace.*
