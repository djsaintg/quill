"""Small, fast checks of Quill's building blocks. Run: .venv/bin/python -m unittest"""
import json
import os
import tempfile
import unittest

from quill import settings, sessions
from quill.characters import persona_note
from quill.engine import resume_request, strip_resume
from quill.sprites import CHARACTERS, FACES, check, sprite

def read(path):
    with open(path) as f:
        return f.read()


def write(path, text):
    with open(path, "w") as f:
        f.write(text)


ID = "69a331b8-d094-45c6-b06e-5d44efafe38c"


class ResumeFlags(unittest.TestCase):
    def test_strip_resume(self):
        self.assertEqual(strip_resume(["-c", "--model", "x", "-r", "abc", "--resume=z"]), ["--model", "x"])

    def test_continue_goes_on_to_claude(self):
        self.assertEqual(resume_request(["-c"]), (["-c"], None))
        self.assertEqual(resume_request(["--c"]), (["-c"], None))
        self.assertEqual(resume_request(["--continue"]), (["--continue"], None))

    def test_resume_on_its_own_opens_the_list(self):
        for args in (["-r"], ["--resume"], ["--r"], ["--resume", "--model", "x"]):
            rest, search = resume_request(args)
            self.assertEqual(search, "", args)
            self.assertNotIn("--resume", rest)
        self.assertEqual(resume_request(["--resume", "--model", "x"])[0], ["--model", "x"])

    def test_resume_with_an_id_goes_on_to_claude(self):
        self.assertEqual(resume_request(["--resume", ID]), (["--resume", ID], None))
        self.assertEqual(resume_request([f"--resume={ID}"]), (["--resume", ID], None))

    def test_resume_with_a_word_searches(self):
        self.assertEqual(resume_request(["-r", "librewolf"]), ([], "librewolf"))


class Persona(unittest.TestCase):
    def test_each_names_itself_and_the_other(self):
        q, p = persona_note("quill"), persona_note("plume")
        self.assertIn("you are Quill (he/him)", q)
        self.assertIn("You are not Plume", q)
        self.assertIn("you are Plume (she/her)", p)
        self.assertIn("You are not Quill", p)
        self.assertNotIn("]\n\n", q + p)  # would break strip_quill_note


class QuillNotes(unittest.TestCase):
    def test_strip(self):
        self.assertEqual(sessions.strip_quill_note("[Quill note: switched. x]\n\nhello"), "hello")
        self.assertEqual(sessions.strip_quill_note("[Quill note: closing, wrap up. rule]"), "")
        self.assertEqual(sessions.strip_quill_note("plain [text]\n\nhere"), "plain [text]\n\nhere")

    def test_history_hides_notes(self):
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
            for content in ("[Quill note: switched. who]\n\nhi there", "[Quill note: closing, wrap up.]"):
                f.write(json.dumps({"type": "user", "message": {"content": content}}) + "\n")
            f.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "yo"}]}}) + "\n")
        try:
            self.assertEqual(sessions.transcript_file(f.name), [("you", "hi there"), ("quill", "yo")])
        finally:
            os.unlink(f.name)


class Rules(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "config.md")

    def test_new_file_has_the_built_ins_with_their_defaults(self):
        rules = settings.load(self.path)
        self.assertTrue(os.path.exists(self.path))
        self.assertEqual([(n, on) for n, on, _ in rules], [("Wrap up", True), ("Test repos", False)])
        self.assertEqual(settings.parse(read(self.path)), rules)

    def test_only_rules_that_are_on_are_told_to_claude(self):
        note = settings.system_note(self.path)
        self.assertIn("Wrap up: When the user says", note)
        self.assertNotIn("Test repos:", note)
        self.assertIn("config.md", note)

    def test_your_edits_are_kept(self):
        settings.load(self.path)
        text = read(self.path).replace("- [ ] **Test repos**", "- [x] **Test repos**")
        text += "- [x] **Mine**: Always say hi.\n  And bye.\n"
        write(self.path, text)
        self.assertEqual(settings.rule("test repos", self.path)[0], True)
        self.assertEqual(settings.rule("Mine", self.path), (True, "Always say hi. And bye."))
        self.assertIn("Mine: Always say hi. And bye.", settings.system_note(self.path))

    def test_a_deleted_built_in_comes_back_and_nothing_else_changes(self):
        write(self.path, "# My notes\n\n- [ ] **Wrap up**: my own words\n")
        rules = settings.load(self.path)
        self.assertEqual(rules[0], ("Wrap up", False, "my own words"))
        self.assertEqual(rules[1][0], "Test repos")
        text = read(self.path)
        self.assertTrue(text.startswith("# My notes\n\n- [ ] **Wrap up**: my own words\n"))
        self.assertEqual(text.count("**Test repos**"), 1)


class Faces(unittest.TestCase):
    def test_every_face_fits_and_uses_known_colours(self):
        for name, face in FACES.items():
            self.assertEqual([len(r) for r in face], [8] * 5, name)
            for who in CHARACTERS:
                check(sprite(who, name, "oops"))

    def test_loading_eyes_go_round(self):
        eyes = [tuple(FACES[f"load{g}1"][1:3]) for g in range(4)]
        self.assertEqual(len(set(eyes)), 4)  # four different frames
        for f in eyes:
            self.assertEqual("".join(f).count("a"), 6)  # 3 of 4 pixels lit, in each eye

    def test_plume_has_no_lashes_through_her_x_eyes(self):
        self.assertEqual(sprite("plume", "oops")[7][4:12], "atattata")


if __name__ == "__main__":
    unittest.main()
