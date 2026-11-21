"""Quill end to end, with tests/fake_claude.py standing in for Claude Code.

Runs the real app headless (Textual's test mode) in a throwaway config, cache and
~/.claude folder, so nothing of yours is read or changed.
"""
import asyncio
import json
import os
import shlex
import shutil
import sys
import tempfile
import time
import unittest

from quill import sessions, settings, sudo
from textual.widgets import Button

from quill.app import QuillApp

HERE = os.path.dirname(os.path.abspath(__file__))
OLD_ID = "11111111-2222-3333-4444-555555555555"


class AppTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="quill-test-")
        cfg = os.path.join(self.tmp, "config")
        os.makedirs(cfg)
        self.saved = (sudo.CONFIG, settings.PATH, sessions.CACHE, sessions.TITLES, os.getcwd(),
                      dict(os.environ))
        sudo.CONFIG = os.path.join(cfg, "config.json")
        settings.PATH = os.path.join(cfg, "config.md")
        sessions.CACHE = os.path.join(self.tmp, "cache", "attribution.json")
        sessions.TITLES = os.path.join(self.tmp, "cache", "chats.json")
        with open(sudo.CONFIG, "w") as f:
            json.dump({"character": "plume", "user_name": "Tester"}, f)
        self.log = os.path.join(self.tmp, "fake.log")
        fake = os.path.join(self.tmp, "claude")
        with open(fake, "w") as f:
            f.write(f"#!/bin/sh\nexec {shlex.quote(sys.executable)} "
                    f"{shlex.quote(os.path.join(HERE, 'fake_claude.py'))} \"$@\"\n")
        os.chmod(fake, 0o755)
        os.environ.update(QUILL_CLAUDE_BIN=fake, FAKE_LOG=self.log, QUILL_AS="plume",
                          CLAUDE_CONFIG_DIR=os.path.join(self.tmp, "claude-home"))
        self.work = os.path.join(self.tmp, "project")
        os.makedirs(self.work)
        os.chdir(self.work)

    def tearDown(self):
        sudo.CONFIG, settings.PATH, sessions.CACHE, sessions.TITLES, cwd, env = self.saved
        os.chdir(cwd)
        os.environ.clear()
        os.environ.update(env)
        shutil.rmtree(self.tmp, ignore_errors=True)

    # helpers
    def sent(self):
        """What Quill sent to Claude Code: (argv lists, user messages)."""
        argv, said = [], []
        if os.path.exists(self.log):
            with open(self.log) as f:
                for line in f:
                    o = json.loads(line)
                    if "argv" in o:
                        argv.append(o["argv"])
                    elif o.get("type") == "user":
                        said.append(o["message"]["content"])
        return argv, said

    async def until(self, pilot, cond, secs=8):
        t = time.monotonic()
        while time.monotonic() - t < secs:
            if cond():
                return True
            await pilot.pause(0.05)
        self.fail("timed out waiting")

    async def type(self, pilot, app, text):
        app.query_one("#input").load_text(text)
        await pilot.press("enter")

    def old_chat(self, folder):
        """An earlier chat saved by 'Claude Code', so the resume list has something in it."""
        d = sessions.project_dir(folder)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, f"{OLD_ID}.jsonl"), "w") as f:
            f.write(json.dumps({"type": "user", "cwd": folder,
                                "message": {"content": "fix the flux capacitor"}}) + "\n")
            f.write(json.dumps({"type": "ai-title", "aiTitle": "Flux capacitor repair",
                                "sessionId": OLD_ID}) + "\n")

    # tests
    async def test_chat_reply_and_faces(self):
        app = QuillApp([])
        async with app.run_test(size=(120, 40)) as pilot:
            await self.until(pilot, lambda: app.engine_ready.is_set())
            argv = self.sent()[0][0]
            note = argv[argv.index("--append-system-prompt") + 1]
            self.assertIn("you are Plume (she/her)", note)
            self.assertIn("Wrap up: ", note)
            self.assertNotIn("Test repos: ", note)  # off unless you turn it on
            await self.type(pilot, app, "slow fail please")
            await self.until(pilot, lambda: app.busy)
            await self.until(pilot, lambda: (app.last_frame or ("",))[0].startswith("load"))
            await self.until(pilot, lambda: app.last_frame and app.last_frame[0] == "oops")
            await self.until(pilot, lambda: not app.busy)
            self.assertIn("echo: slow fail please", app.turn_text)
            self.assertEqual(app.log_items[-1][0], "quill")

    async def test_exit_wraps_up_then_closes(self):
        app = QuillApp([])
        async with app.run_test(size=(120, 40)) as pilot:
            await self.until(pilot, lambda: app.engine_ready.is_set())
            await self.type(pilot, app, "hello")
            await self.until(pilot, lambda: not app.busy and app.log_items[-1][0] == "quill")
            await self.type(pilot, app, "/exit")
            await self.until(pilot, lambda: app.closing_at is not None)
            said = self.sent()[1][-1]
            self.assertTrue(said.startswith("[Quill note: the user is closing Quill now, so wrap up."))
            self.assertIn("Wrapped up", app.turn_text)
            await pilot.click(next(b for b in app.query(Button) if b.name == "wr-close"))
            await self.until(pilot, lambda: app.return_code == 77)

    async def test_exit_with_nothing_said_closes_straight_away(self):
        app = QuillApp([])
        async with app.run_test(size=(120, 40)) as pilot:
            await self.until(pilot, lambda: app.engine_ready.is_set())
            await self.type(pilot, app, "/exit")
            await self.until(pilot, lambda: app.return_code == 77)
        self.assertEqual(self.sent()[1], [])

    async def test_wrap_up_switched_off(self):
        settings.load()
        with open(settings.PATH) as f:
            text = f.read().replace("- [x] **Wrap up**", "- [ ] **Wrap up**")
        with open(settings.PATH, "w") as f:
            f.write(text)
        app = QuillApp([])
        async with app.run_test(size=(120, 40)) as pilot:
            await self.until(pilot, lambda: app.engine_ready.is_set())
            await self.type(pilot, app, "hello")
            await self.until(pilot, lambda: not app.busy and app.log_items[-1][0] == "quill")
            await self.type(pilot, app, "/terminal")
            await self.until(pilot, lambda: app.return_code == 3)
        self.assertEqual(self.sent()[1], ["hello"])

    async def test_resume_flag_lists_chats_and_a_number_opens_one(self):
        self.old_chat(self.work)
        app = QuillApp(["--r"])
        async with app.run_test(size=(120, 40)) as pilot:
            await self.until(pilot, lambda: app.dialog and app.dialog["kind"] == "chats")
            self.assertIn("Flux capacitor repair", app.override)
            await self.type(pilot, app, "1")
            await self.until(pilot, lambda: "--resume" in (self.sent()[0] or [[]])[-1])
            argv = self.sent()[0][-1]
            self.assertEqual(argv[argv.index("--resume") + 1], OLD_ID)

    async def test_typed_resume_search_and_continue(self):
        self.old_chat(self.work)
        app = QuillApp([])
        async with app.run_test(size=(120, 40)) as pilot:
            await self.until(pilot, lambda: app.engine_ready.is_set())
            await app.action_stop()  # close the start-up picker
            await self.type(pilot, app, "--resume nothing-like-this")
            await self.until(pilot, lambda: "No earlier chats" in (app.override or ""))
            await self.type(pilot, app, "/resume flux")
            await self.until(pilot, lambda: app.dialog and app.dialog["kind"] == "chats")
            await app.action_stop()
            await self.type(pilot, app, "-c")
            await self.until(pilot, lambda: "--resume" in self.sent()[0][-1])

    async def test_character_switch_mid_chat_is_told_once(self):
        app = QuillApp([])
        async with app.run_test(size=(120, 40)) as pilot:
            await self.until(pilot, lambda: app.engine_ready.is_set())
            await app.action_stop()
            await self.type(pilot, app, "/character quill")
            await self.type(pilot, app, "one")
            await self.until(pilot, lambda: not app.busy and len(self.sent()[1]) == 1)
            await self.type(pilot, app, "two")
            await self.until(pilot, lambda: not app.busy and len(self.sent()[1]) == 2)
            one, two = self.sent()[1]
            self.assertTrue(one.startswith("[Quill note: the user switched characters."))
            self.assertIn("you are Quill (he/him)", one)
            self.assertEqual(two, "two")

    async def test_scrolled_up_bubble_stays_put_while_it_updates(self):
        app = QuillApp([])
        async with app.run_test(size=(120, 40)) as pilot:
            await self.until(pilot, lambda: app.engine_ready.is_set())
            await app.action_stop()
            bubble = app.query_one("#bubble")
            app.new_turn()
            app.busy = True
            app.add_text("\n\n".join(f"line {i}" for i in range(80)), new_block=True)
            app.show_reply()
            await self.until(pilot, lambda: bubble.max_scroll_y > 20 and bubble.scroll_y == bubble.max_scroll_y)
            bubble.scroll_to(y=5, animate=False)
            await pilot.pause(0.2)
            for i in range(3):  # more arrives while you read
                app.add_text(f"\n\nmore {i}")
                app.show_reply()
                await pilot.pause(0.25)
            self.assertEqual(bubble.scroll_y, 5)
            bubble.scroll_end(animate=False)
            await pilot.pause(0.2)
            app.add_text("\n\n" + "\n\n".join(f"tail {i}" for i in range(10)))
            app.show_reply()
            await self.until(pilot, lambda: bubble.scroll_y == bubble.max_scroll_y and "tail 9" in app.turn_text)
            app.busy = False


if __name__ == "__main__":
    unittest.main()
