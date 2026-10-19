"""One-off script: stitches the per-turn SAPI wavs (made by gen_voices.ps1)
into data/sample.wav with 0.7s silence between turns, and writes
data/reference.txt (the exact script) and data/keywords.txt.

Run: python generate_audio.py
"""
import wave
import struct
from pathlib import Path

ROOT = Path(__file__).parent
TURNS_DIR = ROOT / "data" / "_turns"
SAMPLE_WAV = ROOT / "data" / "sample.wav"
REFERENCE_TXT = ROOT / "data" / "reference.txt"
KEYWORDS_TXT = ROOT / "data" / "keywords.txt"

GAP_SECONDS = 0.7

SCRIPT = [
    ("David", "Hi everyone, thanks for joining. I wanted to talk about planning our team offsite for next quarter."),
    ("Zira", "That sounds great. Do we have a location in mind yet, or are we still deciding on that?"),
    ("David", "We're leaning towards a mountain lodge, somewhere quiet with good hiking trails nearby for everyone to enjoy."),
    ("Zira", "I love that idea. We should also plan a few team building activities, maybe a cooking class or trivia night."),
    ("David", "Good point. Let's budget three days total, with one day dedicated purely to workshops and planning sessions."),
    ("Zira", "Should we invite the remote employees too, or keep this limited to the people in the main office?"),
    ("David", "Definitely invite everyone. We can cover travel costs so nobody feels left out of the offsite."),
    ("Zira", "Perfect, I will start a shared document and send out a survey to gather everyone's availability this week."),
]

KEYWORDS = [
    "offsite", "quarter", "mountain", "lodge", "hiking", "cooking",
    "trivia", "workshops", "remote", "travel", "survey", "budget",
]


def load_turn(path: Path):
    with wave.open(str(path), "rb") as w:
        params = w.getparams()
        frames = w.readframes(w.getnframes())
    return params, frames


def main():
    turn_files = sorted(TURNS_DIR.glob("turn_*.wav"))
    if len(turn_files) != len(SCRIPT):
        raise SystemExit(
            f"Expected {len(SCRIPT)} turn wavs in {TURNS_DIR}, found {len(turn_files)}. "
            "Run gen_voices.ps1 first."
        )

    first_params, _ = load_turn(turn_files[0])
    framerate = first_params.framerate
    sampwidth = first_params.sampwidth
    nchannels = first_params.nchannels
    gap_frames = int(GAP_SECONDS * framerate)
    silence = b"\x00" * (gap_frames * sampwidth * nchannels)

    SAMPLE_WAV.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(SAMPLE_WAV), "wb") as out:
        out.setnchannels(nchannels)
        out.setsampwidth(sampwidth)
        out.setframerate(framerate)
        total_seconds = 0.0
        for i, path in enumerate(turn_files):
            params, frames = load_turn(path)
            if (params.framerate, params.sampwidth, params.nchannels) != (framerate, sampwidth, nchannels):
                raise SystemExit(f"{path} has a different audio format than {turn_files[0]}")
            out.writeframes(frames)
            total_seconds += len(frames) / (sampwidth * nchannels) / framerate
            if i != len(turn_files) - 1:
                out.writeframes(silence)
                total_seconds += GAP_SECONDS

    REFERENCE_TXT.write_text(
        "\n".join(f"{speaker}: {text}" for speaker, text in SCRIPT) + "\n",
        encoding="utf-8",
    )
    KEYWORDS_TXT.write_text("\n".join(KEYWORDS) + "\n", encoding="utf-8")

    print(f"Wrote {SAMPLE_WAV} ({total_seconds:.1f}s, {framerate}Hz, {nchannels}ch, {sampwidth*8}-bit)")
    print(f"Wrote {REFERENCE_TXT}")
    print(f"Wrote {KEYWORDS_TXT}")


if __name__ == "__main__":
    main()
