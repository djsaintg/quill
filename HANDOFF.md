# 🤝 Handoff: Quill, 2026-11-20 (evening)

Where things stand for the next chat. **Nothing below is committed yet.** It's all in the working tree on `main`, waiting for testing and approval.
(This repo is public: decide whether this file gets committed, or delete it after the next chat.)

## What was built this chat (all uncommitted)
Full list: CHANGELOG.md → *Unreleased*. In short:

1. **Characters have their own voice** (started before this chat): `PERSONAS` + `persona_note()` in `quill/characters.py`. A `/character` switch mid-chat adds a `[Quill note: …]` to the next message, and `sessions.strip_quill_note()` hides it from history.
2. **`config.md` rules**: `quill/settings.py` creates `~/.config/quill/config.md`, a checklist (`- [x] **Name**: words`). Built in: *Wrap up* (on) and *Test repos* (**off** by default now, it used to be always on). The rules that are on go into the system note, along with where the file is so Claude can tick boxes when asked. `/rules` shows them. Deleted built-ins come back; your edits and your own rules are kept.
3. **Wrap-up on exit**: `/exit`, `/terminal` and Ctrl+Q send `[Quill note: the user is closing Quill now, so wrap up. <rule words>]`. When the answer ends, "Close now / Stay open" appears, and the window closes on its own after 30 s (typing or Esc keeps it open). It skips the wrap-up if nothing was said, if the rule is off, or if Claude isn't running. `/exit now` or Ctrl+Q twice closes right away. If the wrap-up fails or is stopped, Quill stays open.
4. **Faces** (`quill/sprites.py`, `quill/face.py`):
   - `load<gap><dots>`: thinking eyes are 2×2 loading squares with a gap going round clockwise, and the dot mouth still fills in.
   - `oops`: X eyes and a frown. `flash("oops")` shows it for 1.2 s when a step fails, even mid-work. `feel("oops")` shows it when a whole answer fails.
   - Esc (`self.stopping`) no longer looks like a failure.
   - Plume's lashes skip any face with eyes in row 0.
5. **Split `app.py`** (1,506 → 668 lines) into mixins: `reply`, `face`, `asking`, `commands`, `characters`, `projects`, `remote`, `sudo_ui`, plus `settings`, `widgets`, `texts`, `style`. ⚠️ Textual only finds `@on(...)` handlers on real MessagePump classes, so `pressed`, `submitted` and `sudo_pw_entered` must stay in `QuillApp` and hand off to the mixins.
6. **Window title**: `write_tty()` opens `/dev/tty` directly (no more private `_driver`), sets OSC 0, puts the title back every 3 s, saves and restores the terminal's own title (`CSI 22;0t` / `23;0t`), and sets `CLAUDE_CODE_DISABLE_TERMINAL_TITLE=1` for the child. **The real cause of the title reverting wasn't confirmed** (no terminal in Claude's shell to test with). These measures cover both likely causes.
7. **Resume commands like Claude Code's** (asked mid-chat):
   - `engine.resume_request()` handles the flags. `-c`/`--c`/`--continue` go on to Claude Code. `-r`/`--r`/`--resume` alone or with a word open Quill's chat list (searched). `--resume <uuid>` goes on to Claude Code.
   - In chat: `/resume [word]`, `--resume`, `-r`, `/continue`, `-c`, and `/projects` (the old picker).
   - `sessions.chats()` lists every chat with its `ai-title`/`custom-title`, reading only the first and last 2 MB of each file, cached in `~/.cache/quill/chats.json` (~1 s cold, 0.03 s warm for 95 chats / 385 MB).
   - A typed number now picks a row in either list. Before, typing "2" started a chat called "2", and one exists in the history.
8. **Bubble scroll** (asked mid-chat): `reply.flush()` only follows the reply if you're at the bottom. `show()` and `new_turn()` set `self.jump`, so new things still bring you down.
9. Quill kills its Claude Code child in `on_unmount`, however it closes.
10. **Tests**: `tests/test_units.py` (15) and `tests/test_app.py` (8, real app headless against `tests/fake_claude.py`, in throwaway config/cache/claude dirs). Run: `.venv/bin/python -m unittest discover -s tests -t .` → **23 OK** at the end of this chat. One test (`test_chat_reply_and_faces`) failed once with a `MountError` at shutdown, which is now caught in `flush()`. It passed in 4 solo runs and 4 full runs after that.

## What to test by hand (in a real terminal)
1. `plume`: the window/task-bar title says **Plume** and stays that way during a long job. It goes back to normal after `/exit`.
2. Ask something that makes Claude think: watch for the **loading-square eyes**. Make a command fail (e.g. "run `false`"): **X eyes** for a moment.
3. `/character`, then ask "who are you?" It should be Quill now. F2 history shouldn't show the `[Quill note…]`.
4. Scroll up in the bubble during a long answer: it shouldn't pull you down.
5. `/rules`, then ask Plume to "turn on the test repos rule" and check `~/.config/quill/config.md`.
6. `/resume`, `/resume quill`, a number, Older/Newer. `/continue`. From a terminal: `plume -r`, `quill --c`.
7. Make a small change in some project, then `/exit`. Watch the wrap-up (docs, commit, summary), then Close now / Stay open / let the 30 s run out. Also try `/exit now`, and Ctrl+Q twice.

## Checked in a second chat (2026-11-20, later)
- Tests: **23 OK**. Every `self.*` the mixins use resolves to something defined (AST check), all files compile.
- Read through items 1–9 above against the code: all there and wired up. The rules system is live (that chat's system note had *Wrap up* on, *Test repos* off, and the `config.md` pointer).
- ⚠️ **One edge case, not fixed:** `/exit` (or Ctrl+Q) *while Claude is still busy* on another answer. `send()` then queues the wrap-up note into the running turn, and `wrapped()` runs on the **next** `result`. If Claude Code answers the queued note as a separate turn, the first `result` (the old answer) starts the 30 s countdown, and Quill could close in the middle of the real wrap-up. Fix idea: in `close_after_wrap_up`, if `self.busy`, either wait for the current turn to end before sending the note, or tell the user "finishing this step first". Check how the installed Claude Code handles a mid-turn message (folded in vs its own turn) before choosing. Test 7 below should include this case.

## Decisions still open
- After "approved": commit straight to `main` (what the repo has done so far) or a branch + PR, since it's public now? Then probably **v0.5.0**.
- Whether this HANDOFF.md belongs in the public repo.
- Test repos rule now off by default. On this machine that changes nothing, because `~/.claude/CLAUDE.md` has the same rule. Turn it on in `config.md` if Quill should say it too.

## Asked for next (on ROADMAP.md → Next)
- Sent messages (the `#you` line, max 3 rows today) become a wrapping box that grows to 3 rows and then scrolls like the bubble, with the same "don't pull me down while I read" behaviour, so earlier messages can be read back.
- **Send now: Ctrl+X then Ctrl+S** (the user's description of Claude Code's chord). While Quill is busy, a typed message normally waits: it's handed to Claude Code, which reads it once the current step finishes ("Got it. I'll read that as soon as I finish this step"). This chord skips that wait and sends the message straight away. That probably means interrupting the current step (like Esc), then sending at once, and the bubble should say so. Before building, check how the installed Claude Code does it in headless mode, so Quill matches.
- **Up arrow** in the message box recalls your previous message to edit and resend (Claude Code style). It should probably work only when the cursor is on the first line, so moving around a multi-line message still works.

## Ideas noted, not started
- Character voices editable in `config.md` (ROADMAP "Later").
- F2 history that updates live while it's open (ROADMAP "Later"). Today it's a snapshot, and log items only arrive when a turn ends.
