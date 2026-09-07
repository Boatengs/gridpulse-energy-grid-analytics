from pathlib import Path


PUBLIC_SURFACES = [
    Path("app.py"),
    Path("pages/1_Live_Control_Room.py"),
    Path("README.md"),
    Path("LIVE_DASHBOARD.md"),
]


def test_public_surfaces_use_replay_language_not_animation_language() -> None:
    forbidden = ("animated", "animation")
    for path in PUBLIC_SURFACES:
        text = path.read_text(encoding="utf-8").lower()
        for term in forbidden:
            assert term not in text, f"{path} contains forbidden public wording: {term}"
