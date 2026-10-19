import json
import os
import sys

import assemblyai as aai


def main():
    audio_path = sys.argv[1]
    aai.settings.api_key = os.environ["ASSEMBLYAI_API_KEY"]

    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(audio_path)

    if transcript.status == aai.TranscriptStatus.error:
        print(f"Transcription failed: {transcript.error}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps({"text": transcript.text}))


if __name__ == "__main__":
    main()
