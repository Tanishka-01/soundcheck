import sys
import os
import json

import assemblyai as aai


def main():
    if len(sys.argv) != 2:
        print("Usage: python solution.py <audio_file_path>", file=sys.stderr)
        sys.exit(1)

    audio_path = sys.argv[1]

    api_key = os.environ.get("ASSEMBLYAI_API_KEY")
    if not api_key:
        print("ASSEMBLYAI_API_KEY environment variable is not set", file=sys.stderr)
        sys.exit(1)

    aai.settings.api_key = api_key

    config = aai.TranscriptionConfig(speaker_labels=True)
    transcriber = aai.Transcriber(config=config)

    transcript = transcriber.transcribe(audio_path)

    if transcript.status == "error":
        print(f"Transcription failed: {transcript.error}", file=sys.stderr)
        sys.exit(1)

    speakers = []
    for utterance in transcript.utterances or []:
        if utterance.speaker not in speakers:
            speakers.append(utterance.speaker)

    result = {"text": transcript.text, "speakers": speakers}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
