# 📜 Changelog

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
