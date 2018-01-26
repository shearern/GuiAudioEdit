import os
import wave
import subprocess
import struct
import math
import audioop
from datetime import timedelta



class AudioTime(object):
    def __init__(self, frame_num, frame_rate):
        self.frame_num = frame_num
        self.frames_per_sec = frame_rate
    @property
    def ts(self):
        return timedelta(seconds=self.seconds)
    @property
    def seconds(self):
        return float(self.frame_num) / self.frames_per_sec
    def __str__(self):
        return str(self.ts).split(".")[0]


class AudioFrame(object):
    def __init__(self, frame_data, fmt, pos):
        self.data = frame_data
        self.fmt = fmt
        self.pos = pos
    @property
    def values(self):
        '''Return the integer values stored in the audio data'''

        # Unsigned 8-bit
        # TODO: Test
        if self.fmt.samplewidth == 1:
            return tuple([ord(c) for c in self.data])

        # Signed 16-bit
        elif self.fmt.samplewidth == 2:
            return struct.unpack("%ih" % (self.fmt.num_channels), self.data)

        # Signed 24-bit
        elif self.fmt.samplewidth == 3:
            raise NotImplementedError("Don't know how to parse 24-bit samples")

        raise NotImplementedError("Don't know how to parse %d-bit samples" % (self.fmt.samplewidth*8))


    def _value_1(self, sample):

        # Unsigned 8-bit
        # TODO: Test
        if self.fmt.samplewidth == 1:
            if sample >= 0:
                return float(sample) / 127
            else:
                return float(sample) / -127

        # Signed 16-bit
        elif self.fmt.samplewidth == 2:
            if sample >= 0:
                return float(sample) / 32767
            else:
                return float(sample) / -32768

        # Signed 24-bit
        elif self.fmt.samplewidth == 3:
            if sample >= 0:
                return float(sample) / 8388607
            else:
                return float(sample) / -8388608

        else:
            raise NotImplementedError("Don't know how to parse %d-bit samples" % (self.fmt.samplewidth*8))


    @property
    def values_1(self):
        '''Values stored in frame from -1.0 to 1.0'''
        return tuple([self._value_1(v) for v in self.values])




class StdoutWrapper(object):
    def __init__(self, fp):
        self.fp = fp
    def read(self, num=None):
        return self.fp.read(num)
    def close(self):
        return self.fp.close()


def start_ffmpeg(cmd):

    # TODO: Find it
    ffmpeg = r"ffmpeg.exe"

    cmd = [ffmpeg, ] + list(cmd)
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=None)

    return p


class AudioFormat(object):
    def __init__(self):
        self.encoding = None
        self.framerate = None
        self.samplewidth = None
        self.num_channels = None


def get_raw_audio_data(path):

    cmd = (
        '-i', path,
        '-f', 'wav', '-',
    )

    p = start_ffmpeg(cmd)

    wfh = wave.open(StdoutWrapper(p.stdout), 'r')

    fmt = AudioFormat()
    fmt.encoding = os.path.splitext(os.path.basename(path))[1].strip('.')
    fmt.framerate = wfh.getframerate()
    fmt.samplewidth = wfh.getsampwidth()
    fmt.num_channels = wfh.getnchannels()

    frame_num = 0

    frames_at_once = 4096
    frame_size = fmt.samplewidth * fmt.num_channels

    while True:

        # Get more data
        window = wfh.readframes(frames_at_once)

        # Iterate over frames
        for pos in range(0, len(window), frame_size):
            t = AudioTime(frame_num, fmt.framerate)
            yield AudioFrame(window[pos:pos+(frame_size)], fmt, t)
            frame_num += 1


def avg_signal_value(path):



if __name__ == '__main__':

    # First, find average value in signal
    path = r"G:\User Files\Dropbox\SBC Recordings\Archive\2018\2018-01-07 Adult Bible Study\2018-01-07 Adult Bible Study - rec (partial).flac"
    for frame in get_raw_audio_data(path):
        print frame.pos, frame.values_1
