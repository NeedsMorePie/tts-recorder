import argparse
import os
import pyaudio
import wave

from pynput import keyboard


parser = argparse.ArgumentParser(description='Record some audio for TTS training.')
parser.add_argument('mic_idx', type=int, nargs='?', default=None,
                    help='The mic index. Find this by using the `devices` command.')
args = parser.parse_args()

RATE = 44100
CHANNELS = 1
CHUNK_SIZE = 1024
FORMAT = pyaudio.paInt16

OUTPUT_DIR = 'output'
PROGRESS_FILENAME = 'progress.txt'


def get_reference_sample_width(p: pyaudio.PyAudio):
    wavefile = wave.open('reference_audio.wav', 'rb')
    sample_width = wavefile.getsampwidth()
    print('Sample width:', sample_width)
    print('Expected format:', p.get_format_from_width(sample_width))
    print('Expected num channels:', wavefile.getnchannels())
    return sample_width


def get_input(text: str):
    try:
        return input(text).strip()
    except:
        print('\nExiting, sire.')
        return None


def get_sentences():
    with open('ljs_train_text.txt', 'rt', encoding='utf8') as file:
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
    sample_width = get_reference_sample_width(p)

    input_device_idx = args.mic_idx if args.mic_idx is not None else p.get_default_input_device_info().get('index')
    print('Using mic', p.get_device_info_by_index(input_device_idx))

    stream = p.open(format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        input_device_index=input_device_idx,
        output=True,
        frames_per_buffer=CHUNK_SIZE)

    sentences = get_sentences()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    while True:
        command = get_input('Your next sentence, sire? ')
        if command is None:
            break
        if command == 'devices':
            for i in range(p.get_device_count()):
                if p.get_device_info_by_index(i).get('maxInputChannels') > 0:
                    print(p.get_device_info_by_index(i))
            continue
        sentence_idx = get_progress()
        if sentence_idx >= len(sentences):
            print('You are done, sire.')
            break

        print('')
        print('>', sentences[sentence_idx])
        print('')
        if get_input('Practice now. Press enter to start recording.') is None:
            break

        print('Recording... Press space to stop.')
        chunks = []
        pressed_keys = []
        def on_press(key):
            if key == keyboard.Key.space:
                pressed_keys.append(key)
        with keyboard.Listener(on_press=on_press):
            while not pressed_keys:
                try:
                    chunk = stream.read(CHUNK_SIZE)
                except:
                    break
                chunks.append(chunk)

        print('Replaying...')
        for chunk in chunks:
            stream.write(chunk)
        
        wavefile = wave.open(os.path.join(OUTPUT_DIR, str(sentence_idx) + '.wav'), 'wb')
        wavefile.setnchannels(CHANNELS)
        wavefile.setsampwidth(sample_width)
        wavefile.setframerate(RATE)
        wavefile.writeframes(b''.join(chunks))
        wavefile.close()

        write_progress(sentence_idx + 1)

    stream.close()
    p.terminate()


if __name__ == '__main__':
    main()
