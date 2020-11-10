# Copyright 2016-2020 by John Bauer
# Distributed under the Apache License 2.0

# TO THE EXTENT PERMITTED BY LAW, THE SOFTWARE IS PROVIDED "AS IS",
# WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
# LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
# PARTICULAR PURPOSE, TITLE AND NON-INFRINGEMENT. IN NO EVENT SHALL
# THE COPYRIGHT HOLDERS OR ANYONE DISTRIBUTING THE SOFTWARE BE LIABLE
# FOR ANY DAMAGES OR OTHER LIABILITY, WHETHER IN CONTRACT, TORT OR
# OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE
# OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""
Remaps the song's BPM to a new BPM.

This often has the side effect of removing a lot of gimmicks.

Only works on .sm files for now.  Reading .ssc or .dwi is not supported.

TODO: we could also reverse it and add gimmicks
"""

import argparse
import copy
import math
import re

# 2/3 compatibility
try:
    xrange
except NameError:
    xrange = range

def numbered_list(value, key_name):
    """
    Converts a numbered list of the form X1=Y1, X2=Y2, ...
    into [(X1, Y1), (X2, Y2), ...]
    Useful for reading BPMS and STOPS
    """
    pairs = []
    value = value.strip()
    if not value:
        return pairs
    items = value.split(",")
    for item in items:
        pieces = item.split("=")
        if len(pieces) != 2:
            raise RuntimeError("Illegal format for %s" % key_name)
        pieces = [float(x.strip()) for x in pieces]
        pairs.append(tuple(pieces))
    return pairs

class Simfile(object):
    def __init__(self, pairs):
        """
        Keeps track of a list of key/value pairs for the simfile.
        Also keeps offset/stops/bpms separately to make processing easier.
        """
        # TODO: make this an ordered dictionary
        self.pairs = pairs

        self.offset = 0.0
        self.stops = []
        self.bpms = None

        for pair in pairs:
            if pair[0].lower() == "offset":
                self.offset = float(pair[1])
            if pair[0].lower() == "bpms":
                self.bpms = numbered_list(pair[1], "BPMS")
            if pair[0].lower() == "stops":
                self.stops = numbered_list(pair[1], "STOPS")

        if not self.bpms:   # None or empty
            raise RuntimeError("Simfile doesn't have a BPM")

    def update_bpms(self, offset, bpms, stops):
        """
        Given new text for the bpms and stops, updates the internal timing.
        Updates both the pairs representation and the bpms/stops timing.
        """
        if offset is not None:
            self.offset = float(offset)
        self.bpms = numbered_list(bpms, "BPMS")
        self.stops = numbered_list(stops, "STOPS")
        for i in xrange(len(self.pairs)):
            if self.pairs[i][0].lower() == "bpms":
                self.pairs[i] = ("BPMS", bpms)
            elif self.pairs[i][0].lower() == "stops":
                self.pairs[i] = ("STOPS", stops)
            elif offset is not None and self.pairs[i][0].lower() == "offset":
                self.pairs[i] = ("OFFSET", offset)

    def beat(self, time):
        """
        Converts a time to a beat
        """
        if time == -self.offset:
            return 0.0
        if time < -self.offset:
            return (time + self.offset) / (60. / self.bpms[0][1])
        # has to be a positive beat at this point.
        # need to account for bpm changes and stops
        # TODO: account for changes & stops
        for previous, current in zip(self.bpms[:-1], self.bpms[1:]):
            raise RuntimeError("TODO")
        if len(self.stops) > 0:
            raise RuntimeError("TODO")
        return (time + self.offset) / (60. / self.bpms[0][1])

    def time(self, beat):
        """
        Converts a beat to a time.
        """
        if beat == 0:
            return -self.offset
        if beat < 0:
            return -self.offset + beat * 60. / self.bpms[0][1]
        if beat > 0:
            time = -self.offset
            current_beat = 0
            # TODO: test bpm changes
            for previous, current in zip(self.bpms[:-1], self.bpms[1:]):
                if current[0] > beat:
                    time = time + (beat - current_beat) * (60.0 / previous[1])
                    current_beat = beat
                    break
                else:
                    time = time + (current[0] - current_beat) * (60.0 / previous[1])
                    current_beat = current[0]
            # any leftover time comes from the last bpm
            # (which may be the only bpm)
            if current_beat < beat:
                bpm = self.bpms[-1]
                time = time + (beat - current_beat) * (60.0 / bpm[1])
            # TODO: test stops
            for stop in self.stops:
                if stop[0] < beat:
                    time = time + stop[1]
            return time

all_zeros = re.compile("^0+$")

def combine_steps(A, B, mode, chart, m_num, s_num):
    if len(A) != len(B):
        raise RuntimeError("Step of unexpected length: (%s %s %d %d)" % (mode, chart, m_num, s_num))
    if all_zeros.match(A):
        return B
    if all_zeros.match(B):
        return A
    step = []
    for i, j in zip(A, B):
        if i == '0':
            step.append(j)
        elif j == '0':
            step.append(i)
        elif i == '2' and j == '3':
            print("Warning: turned a very short hold into a tap at %s %s (%d %d)" % (mode, chart, m_num, s_num))
            step.append('1')
        else:
            # TODO: If there is an end hold followed immediately but a
            # start hold, we can separate them by the "snap"
            # However, that might require a bit of a redoing
            raise RuntimeError("Cannot combine steps %s %s of %s %s in (%d %d)" % (A, B, mode, chart, m_num, s_num))
    step = "".join(step)
    print("Warning: combined steps %s, %s of %s %s to get %s at (%d %d)" % (A, B, mode, chart, step, m_num, s_num))
    return step

def fix_stepchart(old_simfile, new_simfile, old_chart, snap):
    chart_pieces = [x.strip() for x in old_chart.split(":")]
    measures = [x.strip() for x in chart_pieces[5].strip().split(",")]
    interesting_steps = []
    for m_num, measure in enumerate(measures):
        steps = [x.strip() for x in measure.split("\n")]
        for s_num, step in enumerate(steps):
            step = step.strip()
            if all_zeros.match(step):
                continue
            old_beat = m_num * 4 + s_num * 4.0 / len(steps)
            old_time = old_simfile.time(old_beat)
            interesting_steps.append( (old_time, step) )

    new_steps = [(new_simfile.beat(x[0]), x[1]) for x in interesting_steps]
    new_steps = [(round(x[0] * snap / 4.0) * 4.0 / snap, x[1]) for x in new_steps]

    if len(new_steps) == 0:
        raise RuntimeError("Empty steps")

    blank = "0" * len(new_steps[0][1])
    # TODO: check that all steps are the same length?

    num_measures = int(math.floor(new_steps[-1][0] / 4.0) + 1)
    new_measures = [[] for _ in xrange(num_measures)]
    for measure in new_measures:
        for i in xrange(snap):
            measure.append(blank)

    # TODO: could simplify empty measures

    for step in new_steps:
        m_num = int(math.floor(step[0] / 4.0))
        s_num = int(round((step[0] - m_num * 4.0) * snap / 4))
        new_measures[m_num][s_num] = combine_steps(new_measures[m_num][s_num], step[1], chart_pieces[0], chart_pieces[2], m_num, s_num)


    measure_text = ["\n".join(x) for x in new_measures]
    chart_text = "\n,\n".join(measure_text)
    chart_pieces[5] = chart_text
    return ":\n".join(chart_pieces)
    

def fix_notes(old_simfile, new_simfile, snap):
    for i in xrange(len(new_simfile.pairs)):
        if new_simfile.pairs[i][0].lower() == "notes":
            new_chart = fix_stepchart(old_simfile, new_simfile, new_simfile.pairs[i][1], snap)
            new_simfile.pairs[i] = (new_simfile.pairs[i][0], new_chart)

def read_simfile(filename):
    pairs = []
    lines = open(filename).readlines()
    key = None
    value = None
    for i in xrange(len(lines)):
        line = lines[i]
        comment = line.find("//")
        if comment >= 0:
            line = line[:comment]
        line = line.strip()
        if key is None:
            key_start = line.find("#")
            if key_start < 0:
                # still not in a key, so no need to save the text
                continue
            key_start = key_start + 1
            key_end = line[key_start:].find(":") + key_start
            if key_end < 0:
                raise RuntimeError("Key spanned multiple lines")
            if key_start == key_end:
                raise RuntimeError("Empty key #:")
            key = line[key_start:key_end]
            line = line[key_end+1:]
        # now we are in a key.  save text and keep going
        if value is None:
            value = ""
        value_end = line.find(";")
        if value_end >= 0:
            value = value + line[:value_end]
            pairs.append( (key, value) )
            key = None
            value = None
        else:
            value = value + "\n" + line
    return Simfile(pairs)

def fix_bg_changes(old_simfile, new_simfile):
    index = None
    for i in xrange(len(new_simfile.pairs)):
        if new_simfile.pairs[i][0].lower() == "bgchanges":
            index = i
            break
    if index is None:
        # no bgchanges to fix
        return

    changes = new_simfile.pairs[index][1].split(",")
    changes = [x for x in changes if x]
    new_changes = []
    for change in changes:
        beat, effect = change.strip().split("=", 1)
        time = old_simfile.time(float(beat))
        new_beat = new_simfile.beat(time)
        new_changes.append("%0.3f=%s" % (new_beat, effect))
    new_simfile.pairs[index] = (new_simfile.pairs[index][0], ",\n".join(new_changes))

def write_simfile(filename, simfile):
    fout = open(filename, "w")
    for i in simfile.pairs:
        fout.write("#%s:%s;\n" % (i[0], i[1]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Remap BPMs')
    parser.add_argument('--input', default=None, required=True,
                        help="Which file to read for input")
    parser.add_argument('--output', default=None, required=True,
                        help="Where to write the translated file")
    parser.add_argument('--bpms', default=None, required=True,
                        help="BPM to use: use sm format")
    parser.add_argument('--stops', default="",
                        help="STOPS to use: use sm format")
    parser.add_argument('--offset', default=None,
                        help="New offset to use (blank = keep existing)")
    parser.add_argument('--snap', default=16, type=int,
                        help="Beat division for snapping the steps")
    args = parser.parse_args()

    old_simfile = read_simfile(args.input)
    new_simfile = copy.deepcopy(old_simfile)
    new_simfile.update_bpms(args.offset, args.bpms, args.stops)
    fix_bg_changes(old_simfile, new_simfile)
    fix_notes(old_simfile, new_simfile, args.snap)
    write_simfile(args.output, new_simfile)

