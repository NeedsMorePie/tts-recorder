# tts-recorder
Records sentences/utterances for TTS training.

## Requirements

* Python packages
  * Librosa
  * pysoundfile
  * pyaudio
  * pynput
* Conda installable
  * ffmpeg

## Supported commands when it asks for your next sentence

* `devices`
  * Lists all the devices for recording. These can be passed in as the first arg. E.g. `python -m main <device idx>`.
* `undo`
  * Undoes progress and allows you to re-record the previous sentence.
* `assemble`
  * Outputs metadata.csv in the output directory.
