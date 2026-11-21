# 📜 Changelog

## Unreleased
- **Wrap-up on exit:** `/exit`, `/terminal` and Ctrl+Q first ask Claude to bring every changed project's docs up to date and commit/push where your own rules allow; the summary stays up for 30 s (Close now / Stay open, or just type). Esc stops the wrap-up, `/exit now` or Ctrl+Q twice skips it, and a chat where nothing was said closes straight away
- **`config.md` rules:** `~/.config/quill/config.md` is a checklist of rules Claude follows in every chat; you (or your character) tick them on and off, reword them or add your own. Built in: *Wrap up* (on) and *Test repos* (now **off** by default, it was always on). `/rules` shows them
- **Characters have their own voice:** Quill (he/him) is upbeat and practical, Plume (she/her) calm and thoughtful; `/character` mid-chat tells Claude about the switch with your next message. Only the tone changes, never how carefully the work is done
- **New faces:** loading-square eyes while thinking, ✗ eyes for a moment when a step fails (and with a frown when a whole answer fails); pressing Esc no longer looks like a failure
- **Every earlier chat:** `/resume` (also `--resume`, `-r`, `/resume <word>`) lists all chats with their titles, a page at a time, searchable; `/continue` / `-c` opens the last chat in this folder; `quill -r` / `plume --resume [word]` start on that list, `--c` / `--r` work like `-c` / `-r`. The old project list is `/projects`
- **Typing a number** in the project or chat list now picks that row (it used to start a new chat called "2")
- **Read at your own pace:** scrolled up in the bubble, it now updates quietly instead of jumping to the bottom; a new answer or question still brings you down
- **Window title** names whoever's at the desk and stays that way (Claude Code is told not to set titles, and Quill puts its own back every few seconds); your terminal's own title comes back when Quill closes
- Quill always stops its Claude Code when it closes, however it closes
- Under the hood: `app.py` (1,500 lines) split into small parts (`reply`, `face`, `asking`, `commands`, `characters`, `projects`, `remote`, `sudo_ui`, `settings`, `widgets`, `texts`, `style`); 23 tests in `tests/` (`.venv/bin/python -m unittest discover -s tests -t .`), the app ones driving Quill against a fake `claude`
- **Live steps in the bubble:** while Claude works you see each step as it happens (`⠋ Reading app.py…`), then a one-liner once it's done (`✓ Read app.py · 130 lines`, `✗ Ran: … · exit code 2`), with Claude's notes in between; a helper's step shows what the helper is doing

## v0.4.0 — 2026-11-20
- **Plume**, a second character (a feather instead of an antenna), with her own expressions
- First-start chooser: Quill on the left in `classic` colours, Plume on the right in `aurora`; `/character` switches, and the `quill` / `plume` commands open their own character
- Colour schemes per character: `/theme classic|aurora` (aurora = Tokyo Night purples)
- First launch asks your name and suggests the one Claude already knows; `/name`
- Project list in the greeting: the next roadmap item (or where Claude left off) for each recent project; chats started in a folder of projects are filed under the project they worked in; continue the last chat or start fresh
- Multi-line input: `\` + Enter or Ctrl+J
- Permissions: auto mode, like a normal Claude Code session; "don't ask again" covers that level for this chat only and is never saved; several permission requests at once are queued instead of lost
- Sudo asks with a password box even when off ("Run it once")
- Status line shows what's running, for how long, and when Claude's servers go quiet
- Desktop pop-ups when you're needed or a long job finishes (`/notify`)
- `/remote-control` (`/rc`) carries the chat to the Claude app or claude.ai
- `/exit` closes the terminal window too; `/terminal` goes back to the prompt
- Throwaway "test repo" rule built into Claude's instructions
- README: disclaimer, Settings, Privacy

## v0.2.0 — 2026-11-19
- Copy and paste (drag + Ctrl+C, F3), half-size Quill in small windows, wrapped commands in prompts
- Optional sudo with a password prompt in Quill

## v0.1.0 — 2026-11-19
- First version: Quill with a speech bubble, live moods, permission and question buttons, F2 history
