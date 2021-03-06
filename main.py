import argparse
import glob
import librosa
import math
import os
import pyaudio
import soundfile
import struct
import wave

from pynput import keyboard


parser = argparse.ArgumentParser(description='Record some audio for TTS training.')
parser.add_argument('mic_idx', type=int, nargs='?', default=None,
                    help='The mic index. Find this by using the `devices` command.')
args = parser.parse_args()

RATE = 44100
LJS_RATE = 22050
CHANNELS = 1
CHUNK_SIZE = 1024
FORMAT = pyaudio.paInt16
FORMAT_SOUNDFILE = 'PCM_16'

# The RMS threshold used for stripping empty audio at the beginning and end.
RMS_THRESHOLD = 25.0
# The required minimum average RMS of the stripped audio for it to be considered good enough.
MIN_AVG_RMS = 40.0
# The number of chunks at the beginning and end of each recording to ignore.
# Tapping a keyboard key usually lasts about this long.
CHUNK_IGNORE_PADDING = 4
# The number of chunks to keep around the beginning and end of each stripped chunk.
CHUNK_KEEP_PADDING = 3

OUTPUT_DIR = 'output'
PROGRESS_FILENAME = 'progress.txt'

SHORT_NORMALIZE = (1.0 / 32768.0)


def get_reference_sample_width(p: pyaudio.PyAudio):
    wavefile = wave.open('reference_audio.wav', 'rb')
    sample_width = wavefile.getsampwidth()
    print('Sample width:', sample_width)
    print('Expected format:', p.get_format_from_width(sample_width))
    print('Expected num channels:', wavefile.getnchannels())
    print('Expected sample rate:', wavefile.getframerate())
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


def compute_rms(chunk, sample_width):
    count = len(chunk) / sample_width
    format = "%dh" % (count)
    shorts = struct.unpack(format, chunk)

    sum_squares = 0.0
    for sample in shorts:
        n = sample * SHORT_NORMALIZE
        sum_squares += n * n
    rms = math.pow(sum_squares / count, 0.5)

    return rms * 1000


def filter_chunks(chunks, sample_width):
    max_idx = len(chunks) - 1
    start_idx = CHUNK_IGNORE_PADDING
    end_idx = max_idx - CHUNK_IGNORE_PADDING
    while compute_rms(chunks[start_idx], sample_width) < RMS_THRESHOLD and start_idx < max_idx:
        start_idx = start_idx + 1
    while compute_rms(chunks[end_idx], sample_width) < RMS_THRESHOLD and end_idx > 0:
        end_idx = end_idx - 1
    start_idx = max(start_idx - CHUNK_KEEP_PADDING, 0)
    end_idx = min(end_idx + CHUNK_KEEP_PADDING, max_idx)
    if start_idx < end_idx:
        # + 1 because the end is exclusive.
        result_chunks = chunks[start_idx:end_idx + 1]
        # Check the quality of result chunks.
        avg_rms = 0.0
        for chunk in result_chunks:
            avg_rms = avg_rms + compute_rms(chunk, sample_width)
        avg_rms = avg_rms / len(result_chunks)
        if avg_rms > MIN_AVG_RMS:
            return result_chunks
        else:
            print('Your audio was too quiet. Get closer to the mic, sire.')
    return []


def resample(out_path: str):
    # Resamples to the ljs sample rate.
    data, _ = librosa.load(out_path, sr=LJS_RATE)
    split_ext = os.path.splitext(out_path)
    new_out_path = split_ext[0] + '_' + str(LJS_RATE) + split_ext[1]
    soundfile.write(new_out_path, data, LJS_RATE, subtype=FORMAT_SOUNDFILE)


def get_recorded_sentences():
    sentence_idxs = set()
    for path in glob.glob(os.path.join(OUTPUT_DIR, '*.wav')):
        sentence_idxs.add(int(os.path.splitext(os.path.basename(path))[0].split('_')[0]))
    return sentence_idxs


def assemble(sentences):
    # Outputs the assembled csv.
    lines = []
    for sentence_idx in sorted(list(get_recorded_sentences())):
        lines.append(str(sentence_idx) + '_' + str(LJS_RATE) + '|' + sentences[sentence_idx] + '|' + sentences[sentence_idx] + '\n')
    with open(os.path.join(OUTPUT_DIR, 'metadata.csv'), 'wt') as file:
            file.writelines(lines)


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
        # Get command and multiplex behaviors.
        command = get_input('Your next sentence/command, sire? ')
        if command is None:
            break
        elif command == 'devices':
            for i in range(p.get_device_count()):
                if p.get_device_info_by_index(i).get('maxInputChannels') > 0:
                    print(p.get_device_info_by_index(i))
            continue
        elif command == 'undo':
            write_progress(max(0, get_progress() - 1))
            continue
        elif command == 'assemble':
            assemble(sentences)
            continue

        # Default behavior is to start the recording flow, which consists of:
        # 1. Showing the sentence to read.
        # 2. Recording audio.
        # 3. Processing audio (stripping the start/end of any empty audio).
        # 4. Replaying the audio.
        # 5. Either redo or skip the current sentence.

        sentence_idx = get_progress()
        if sentence_idx >= len(sentences):
            print('You are done, sire.')
            break

        print('')
        print('>', sentences[sentence_idx])
        print('')
        if get_input('Practice now. Press enter to start recording.') is None:
            break

        status = ''
        chunks = []
        while True:
            print('Recording... Press enter to stop.')
            chunks = []
            pressed_keys = []
            def on_press(key):
                if key == keyboard.Key.enter:
                    pressed_keys.append(key)
            with keyboard.Listener(on_press=on_press):
                while not pressed_keys:
                    try:
                        chunk = stream.read(CHUNK_SIZE)
                    except:
                        break
                    chunks.append(chunk)
            chunks = filter_chunks(chunks, sample_width)
            # Bit of a hack, but this absorbs the enter key that was pressed to stop recording.
            get_input('')
            if not chunks:
                print('Sire, your audio was garbage. Please try again.')
                continue

            print('Replaying...')
            for chunk in chunks:
                stream.write(chunk)

            status = get_input('Redo [r] or skip [s] (default is to commit)? ')
            if status == 'r':
                print('')
                print('>', sentences[sentence_idx])
                print('')
            else:
                break

        if status != 's':
            out_path = os.path.join(OUTPUT_DIR, str(sentence_idx) + '.wav')
            wavefile = wave.open(out_path, 'wb')
            wavefile.setnchannels(CHANNELS)
            wavefile.setsampwidth(sample_width)
            wavefile.setframerate(RATE)
            wavefile.writeframes(b''.join(chunks))
            wavefile.close()
            resample(out_path)

        # Commit progress.
        write_progress(sentence_idx + 1)

    stream.close()
    p.terminate()


if __name__ == '__main__':
    main()
