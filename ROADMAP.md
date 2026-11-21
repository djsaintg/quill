# 🗺️ Quill roadmap

Quill (and Plume) is a pixel desk-robot face for Claude Code. What's done is in [CHANGELOG.md](CHANGELOG.md).

## Next
- [ ] Check that messages sent from the Claude app or claude.ai during `/rc` (Remote Control) show up in Quill as "you (remote)"
- [ ] Document using Quill on a phone: SSH into your computer from a terminal app (e.g. Termux) and run `quill`
- [ ] `/exit` while Claude is still busy: wait for the current answer before the wrap-up, so the close countdown can't start early
- [ ] Test the Unreleased changes in a real chat (see HANDOFF.md), then release v0.5.0
- [ ] Your sent messages in a wrapping box that grows to 3 rows, then scrolls like the speech bubble, so you can look back over what you've sent
- [ ] **Send now** (Ctrl+X then Ctrl+S, like Claude Code): while Quill is busy, send your message straight away instead of waiting until the current step is done
- [ ] **Up arrow** in the message box brings back your previous message to edit and send again, like Claude Code
- [ ] Paste images into the message box

## Later / ideas
- [ ] A floating Quill/Plume bubble on Android that talks to Claude Code on your computer
- [ ] More colour schemes and characters
- [ ] Character voices editable in `config.md` too (today only the rules are)
- [ ] F2 history that updates live while it's open
- [ ] macOS support (sudo, window closing and pop-ups use Linux tools today)
- [ ] Other AI back ends besides Claude Code
