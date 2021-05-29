import os
import pyaudio
import wave

from pynput import keyboard


RATE = 44100
CHANNELS = 1
CHUNK_SIZE = 1024
FORMAT = pyaudio.paInt16

OUTPUT_DIR = 'output'
PROGRESS_FILENAME = 'progress.txt'


class KeyboardListener(keyboard.Listener):
    def __init__(self):
        super().__init__()
        self.key_pressed = False

    def on_press(self, _):
        """Overridden."""
        self.key_pressed = True


def get_sentences():
    with open('ljs_train_text.txt', 'rt') as file:
        lines = file.read().split('\n')
    sentences = []
    for line in lines:
        pieces = line.split('|')
        if len(pieces) != 3:
            print('W: Incorrect number of pieces on line.')
            continue
        sentences.append(pieces[1])
    print(len(sentences), 'total sentences.')
    return sentences


def write_progress(progress: int):
    with open(os.path.join(OUTPUT_DIR, PROGRESS_FILENAME), 'wt') as file:
        file.write(str(progress))


def get_progress() -> int:
    try:
        with open(os.path.join(OUTPUT_DIR, PROGRESS_FILENAME), 'rt') as file:
            return int(file.read())
    except:
        write_progress(0)
        return 0


def main():
    # Check against the reference file.
    p  = pyaudio.PyAudio()
    wavefile = wave.open('reference_audio.wav', 'rb')
    print('Expected format:', p.get_format_from_width(wavefile.getsampwidth()))
    print('Expected num channels:', wavefile.getnchannels())

    stream = p.open(format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        output=True,
        frames_per_buffer=CHUNK_SIZE)

    sentences = get_sentences()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    while True:
        try:
            command = input('Your next sentence, sire? ')
        except:
            print('\nExiting, sire.')
            return
        sentence_idx = get_progress()
        if sentence_idx >= len(sentences):
            print('You are done, sire.')
            return
        print(sentences[sentence_idx])

        print('Recording...')
        chunks = []
        keyboard_listener = KeyboardListener()
        keyboard_listener.start()
        while not keyboard_listener.key_pressed:
            try:
                chunk = stream.read(CHUNK_SIZE)
            except:
                continue
            chunks.append(chunk)
        keyboard_listener.stop()

        write_progress(sentence_idx + 1)


if __name__ == '__main__':
    main()
