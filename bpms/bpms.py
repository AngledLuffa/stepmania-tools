"""
Generates an OFFSET and list of BPMS from a list of times.

Estimates how many beats are between each note by using an estimated
BPM.  This is quite preliminary and needs more work, but saving it in
github is a good way to avoid screwing it up while doing that work.

To run:

python bpms.py notes.txt estimate [beats]

notes.txt: a list of offsets in the song
estimate: a bpm to try to match
beats: the starting beat for the first offset.  optional

Output:

offset, bpms which can be copy/pasted into the .sm file
"""

# Copyright 2016 by John Bauer
# Distributed under the Apache License 2.0

# TO THE EXTENT PERMITTED BY LAW, THE SOFTWARE IS PROVIDED "AS IS",
# WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
# LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
# PARTICULAR PURPOSE, TITLE AND NON-INFRINGEMENT. IN NO EVENT SHALL
# THE COPYRIGHT HOLDERS OR ANYONE DISTRIBUTING THE SOFTWARE BE LIABLE
# FOR ANY DAMAGES OR OTHER LIABILITY, WHETHER IN CONTRACT, TORT OR
# OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE
# OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import sys

if __name__ == "__main__":
    filename = sys.argv[1]
    bpm = float(sys.argv[2])
    start_beat = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
    lines = [line.strip() for line in open(filename).readlines()]
    lines = [line.split("#")[0] for line in lines]
    times = [float(line) for line in lines if line]

    current_beat = start_beat
    for index, (start, end) in enumerate(zip(times[:-1], times[1:])):
        beats = round((end - start) / (60. / bpm) * 2) / 2.0
        tempo = 60. / (end - start) * beats
        if index == 0:
            print "#OFFSET:%.4f;" % (-times[0] + (60. / tempo) * current_beat)
            print "#BPMS:"
        continuation = "," if index < len(times) - 2 else ";"
        display_beat = current_beat if index > 0 else 0
        # comment = " # %d" % start
        comment = ""
        print "%.1f=%.4f%s%s" % (display_beat, tempo, continuation, comment)
        current_beat = current_beat + beats



