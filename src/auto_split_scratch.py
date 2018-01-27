import os, sys
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

    if not os.path.exists(path):
        print("ERROR: File doesn't exist: " + path)
        sys.exit(2)

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



class MovingAverage(object):
    '''
    Data collection used to calculate an average over a moving window

    See https://en.wikipedia.org/wiki/Moving_average
    '''

    def __init__(self, size):
        self.__size = size
        self.__values = [None, ] * size
        self.__average = 0
        self.__i = 0

    @property
    def avg(self):
        return self.__average

    def add(self, value):
        '''
        Add a value to the sequence to calculate an average

        param value: Numeric value to add
        :param pop: If true, pop the oldest value off the front of the sequence
        '''
        
        # Store value
        old_value = self.__values[self.__i]
        self.__values[self.__i] = value
        self.__i = (self.__i + 1) % (self.__size)

        # Update Average
        if old_value is None:
            buff_len = self.__i
            if buff_len == 0: # We just wrapped around on the buffer
                buff_len = self.__size
            self.__average = self.__average + ((value - self.__average) / buff_len)
        else:
            self.__average = self.__average + (float(value) / self.__size) - (float(old_value) / self.__size)

        # # TODO: Remove once it looks like math is working
        # try:
        #     self.__calls += 1
        # except AttributeError:
        #     self.__calls = 1
        # if self.__calls % (44100 * 60 * 15) == 0:
        #     # Recalculate average
        #     avg = sum(self.__values) / float(len(self.__values))
        #     print("Recalculating average from %s to %s" % (self.__average, avg))
        #     if self.__average != 0:
        #         print("  error: %0.6f" % (abs(avg-self.__average)/self.__average))
        #     self.__average = avg


class SilencePeriod(object):
    def __init__(self, start):
        self.start = start
        self.end = start


def find_silent_sections(path):

    moving_avg_sec = 15
    min_silence_len = timedelta(seconds=0.25)

    for frame in get_raw_audio_data(path):

        # Init
        if frame.pos.frame_num == 0:

            fmt = frame.fmt

            ch = [{
                'moving_avg': MovingAverage(fmt.framerate*moving_avg_sec),  # Setup moving average get average wave values
                'period': None,
                }, ] * fmt.num_channels

            fill_frames = moving_avg_sec * fmt.framerate

        # Normalize values from 0.0 to 1.0
        sample = [abs(meassure) for meassure in frame.values_1]

        # Consume initial seconds to fill moving average
        # (note: won't detect silence in this first window)
        if frame.pos.frame_num < fill_frames:
            for c in fmt.num_channels:
                ch[c]['moving_avg'].add(sample[c])

        # Rest of the file
        else:
            for c in fmt.num_channels:
                silence_threshold = ch[c]['moving_avg'].avg * 0.05
                is_silent = sample[c] < silence_threshold
                if is_silent:
                    if ch[c]['period'] is None:
                        ch[c]['period'] = SilencePeriod(start=frame.pos)
                    else:
                        ch[c]['period'].end = frame.pos
                else:
                    if ch[c]['period'] is not None:
                        plength = ch[c]['period'].end.ts - ch[c]['period'].start.ts
                        if plength >= min_silence_len:
                            yield ch[c]['period']
                    ch[c]['period'] = None


if __name__ == '__main__':

    # First, find average value in signal
    path = r"C:\Users\nshearer\Downloads\2018-01-07 Adult Bible Study - rec (partial).flac"

    for frame in get_raw_audio_data(path):

        if frame.pos.frame_num % (44100 * 15) == 0:
            print str(frame.pos)

        # For the first 5 seconds, just add the value
        #moving_avg.add(abs(frame.values_1[1]))

        if frame.pos.frame_num > (44100 * 60 * 2):
            break