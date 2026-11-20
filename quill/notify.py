"""Desktop notifications (notify-send), for when Quill's window is in the background."""
import shutil
import subprocess


def send(title, body=""):
    if not shutil.which("notify-send"):
        return
    body = " ".join(body.split())
    if len(body) > 180:
        body = body[:179] + "…"
    try:
        subprocess.Popen(["notify-send", "-a", "Quill", "-i", "utilities-terminal", title, body],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass
