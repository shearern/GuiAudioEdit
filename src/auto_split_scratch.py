import os, sys
import wave
import subprocess
import struct
import math
import audioop
from itertools import islice, izip
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


class AudioFile(object):

    def __init__(self, path):
        self.path = path
        self.encoding = None
        self.framerate = None
        self.samplewidth = None
        self.num_channels = None


    def _start_ffmpeg(self, cmd):
        # TODO: Find it
        ffmpeg = r"ffmpeg.exe"

        cmd = [ffmpeg, ] + list(cmd)
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=None)

        return p


def _nbyte_iterator(data, bytes):
    '''
    Yield n bytes at a time from the data

    _nbyte_iterator('ABCDEF') --> 'AB', 'CD', 'EF'

    :param data: Data to slicer
    :param bytes: How many bytes at once to return
    '''

    # Trying to use islice in case it's faster than indexing in a list

    # Setup iterators to slice through data
    i = iter(data)
    try:
        if bytes == 1:
            while True:
                yield i.next()
        elif bytes == 2:
            while True:
                yield i.next() + i.next()
        elif bytes == 3:
            while True:
                yield i.next() + i.next() + i.next()
        elif bytes == 4:
            while True:
                yield i.next() + i.next() + i.next() + i.next()
        else:
            raise Exception("Don't know how to handle %d bytes" % (bytes))
    except StopIteration:
        return


class AudioFileReader(AudioFile):

    def get_raw_audio_data(self):

        if not os.path.exists(self.path):
            print("ERROR: File doesn't exist: " + self.path)
            sys.exit(2)

        cmd = (
            '-i', path,
            '-f', 'wav',
            '-ac', '1', # Mix down to mono
            '-', # Output to stdout
        )

        p = self._start_ffmpeg(cmd)

        wfh = wave.open(StdoutWrapper(p.stdout), 'r')

        self.encoding = os.path.splitext(os.path.basename(path))[1].strip('.')
        self.framerate = wfh.getframerate()
        self.samplewidth = wfh.getsampwidth()
        self.num_channels = wfh.getnchannels()

        frame_num = 0

        frames_at_once = 1024 * 1024
        frame_size = self.samplewidth * self.num_channels

        while True:

            # Get more data
            window = wfh.readframes(frames_at_once)
            if not window:
                return

            # Iterate over frames
            for i, frame_data in enumerate(_nbyte_iterator(window, frame_size)):
                self.last_frame = AudioFrame(''.join(frame_data), self, AudioTime(frame_num+i, self.framerate))
                yield self.last_frame

            frame_num += len(window)


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
    def __str__(self):
        return '%s to %s' % (self.start.ts, self.end.ts)
    @property
    def length(self):
        return self.end.ts - self.start.ts
    @property
    def frames(self):
        return self.end.frame_num - self.start.frame_num + 1


def find_silent_sections(af):
    '''
    Find periods of silence in the audio file
    
    Note: Assumes mono input (makes analysis much easier)
    
    :param af: Audio file to be read
    :return: Generator of SilencePeriod
    '''

    moving_avg_sec = 15
    min_silence_len = timedelta(seconds=0.25)

    # Setup moving average get average wave values
    avg = None
    period = None
    fill_frames = None

    for frame in af.get_raw_audio_data():

        # if frame.pos.frame_num % (44110 * 15) == 0:
        #     print(str(frame.pos))

        # Init
        if frame.pos.frame_num == 0:
            fmt = frame.fmt
            fill_frames = moving_avg_sec * fmt.framerate
            avg = MovingAverage(fmt.framerate*moving_avg_sec)

        # Normalize values from 0.0 to 1.0
        sample = abs(frame.values_1[0])

        # Consume initial seconds to fill moving average
        # (note: won't detect silence in this first window)
        if frame.pos.frame_num < fill_frames:
            avg.add(sample)

        # Rest of the file
        else:
            silence_threshold = avg.avg * 0.15
            is_silent = sample < silence_threshold
            if is_silent:
                if period is None:
                    period = SilencePeriod(start=frame.pos)
                else:
                    period.end = frame.pos # Extend period to include this frame
            else: # Not silent
                if period is not None:
                    plength = period.end.ts - period.start.ts
                    if plength >= min_silence_len:
                        yield period
                period = None


class Track(SilencePeriod):
    def __init__(self, start, track_num):
        super(Track, self).__init__(start)
        self.track_num = track_num


def calc_track_times(af, min_track_len, max_track_len):
    '''
    Do calculations to split tracks into sizes picking silent periods to split

    Will pick the longest silence between minimum and maximum lengths.

    :param af: Audio file
    :param min_track_len: Minimun length of a track (timedelta)
    :param max_track_len:  Maximium length of track (timedelta)
    :return: Tracks
    '''
    silences = find_silent_sections(af)

    # Get first silense to get format
    first_silence = silences.next()
    framerate = first_silence.start.frames_per_sec

    # Start first track
    start = AudioTime(0, framerate)
    track = Track(start, 1)

    while True:

        track_min_end = track.start.ts + min_track_len
        track_max_end = track.start.ts + max_track_len

        try:
            silences_for_split = list()
            for silence in silences:
                if silence.start.ts > track_min_end:
                    silences_for_split.append(silence)
                if silence.end.ts > track_max_end:
                    break

            longest_silence = max(silences_for_split, key=lambda s: s.length)
            mid_frame_nun = longest_silence.start.frame_num + (longest_silence.frames / 2)
            split_at = AudioTime(mid_frame_nun, framerate)

            track.end = split_at
            yield track

            track = Track(split_at, track.track_num+1)

        except StopIteration:

            # No more silences.  Assuming end of audio file
            track.end = af.last_frame
            yield track
            return


def split_disks(af):
    '''Return tracks split into disks'''

    max_disk_time = timedelta(minutes=70)

    # Organize tracks into disks
    disk_num = 1
    track_num = 1
    disk_end_by = max_disk_time
    for track in calc_track_times(af, min_track_len=timedelta(minutes=7), max_track_len=timedelta(minutes=10)):
        if track.end.ts <= disk_end_by:
            track.disk_num = disk_num
            track.track_num = track_num
            yield track
            track_num += 1
        else:
            disk_start = track.start.ts
            disk_end_by = disk_start + max_disk_time

            disk_num += 1
            track.disk_num = disk_num

            track_num = 1
            track.track_num = track_num

            yield track


if __name__ == '__main__':

    # First, find average value in signal
    path = r"C:\Users\nshearer\Downloads\2018-01-07 Adult Bible Study - rec (partial).flac"
    #path = r"G:\User Files\Dropbox\SBC Recordings\Archive\2018\2018-01-07 Adult Bible Study\2018-01-07 Adult Bible Study - rec (partial).flac"
    af = AudioFileReader(path)

    for track in split_disks(af):
        print "%s - %s\tD%02d T%02d" % (str(track.start), str(track.end), track.disk_num, track.track_num)




        # if frame.pos.frame_num % (44100 * 15) == 0:
        #     print str(frame.pos)
        #
        # # For the first 5 seconds, just add the value
        # #moving_avg.add(abs(frame.values_1[1]))
        #
        # if frame.pos.frame_num > (44100 * 60 * 2):
        #     break