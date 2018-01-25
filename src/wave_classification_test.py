import os
import wave
import subprocess
import struct
import math
from datetime import timedelta

import matplotlib.pyplot as plt

class StdoutWrapper(object):
    def __init__(self, fp):
        self.fp = fp
    def read(self, num=None):
        return self.fp.read(num)
    def close(self):
        return self.fp.close()


def pcm16_to_1(amp):
    if amp >= 0:
        return amp / 32767.0
    else:
        return amp / 32768.0


def amp1_to_db(amp):
    if amp == 0:
        return 0
    elif amp < 0:
        return 10 * math.log10(-1*amp)
    else:
        return 10 * math.log10(amp)


if __name__ == '__main__':

    ffmpeg = r"..\ffmpeg.exe"
    path = r"..\sine.flac"

    cmd = (
        ffmpeg,
        '-i', path,
        '-f', 'wav', '-',
    )

    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=None)

    wav = wave.open(StdoutWrapper(p.stdout), 'r')

    print "framerate:  ", wav.getframerate()
    print "samplewidth:", wav.getsampwidth()
    print "frames:     ", wav.getnframes()

    frames_at_once = wav.getframerate() / 100 # 44100

    graph = list()

    # s16 max: 32767,  min: -32768, zero: 0

    i = 0
    frame = wav.readframes(frames_at_once)
    while frame:

        i += 1

        # Probably using "frame" wrong.  I mean a set of samples...
        samples_captured = len(frame) / wav.getsampwidth()

        frame = struct.unpack("%ih" % (samples_captured* wav.getnchannels()), frame)

        ts = timedelta(seconds=(wav.tell()/wav.getframerate()))

        sample = pcm16_to_1(frame[0])
        graph.append(sample)
        db = amp1_to_db(sample)
        print "%s\t%.02f\t%.02f" % (ts, sample, db)

        frame = wav.readframes(frames_at_once)

    # Plot graph
    plt.figure(1)
    plt.title(os.path.basename(path))
    plt.plot(graph)
    plt.show()
