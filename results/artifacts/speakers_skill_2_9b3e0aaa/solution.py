import sys
import os
import json

import assemblyai as aai


def main():
    audio_path = sys.argv[1]

    aai.settings.api_key = os.environ["ASSEMBLYAI_API_KEY"]

    config = aai.TranscriptionConfig(
        speech_models=["universal-3-5-pro", "universal-2"],
        speaker_labels=True,
    )
    transcriber = aai.Transcriber(config=config)
    transcript = transcriber.transcribe(audio_path)

    if transcript.status == aai.TranscriptStatus.error:
        print(f"Transcription failed: {transcript.error}", file=sys.stderr)
        sys.exit(1)

    speakers = []
    if transcript.utterances:
        for utt in transcript.utterances:
            if utt.speaker not in speakers:
                speakers.append(utt.speaker)

    result = {"text": transcript.text, "speakers": speakers}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
