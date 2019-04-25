import blessings

from .base import NeolithClient

import datetime
import signal
import sys


class Line:

    def __init__(self, text, prefix='>'):
        self.prefix = prefix
        self.text = text
        self.timestamp = datetime.datetime.now()

    def split(self, term):
        lines = []
        line = '{t.white}{time} {t.green}{prefix}{t.normal}'.format(
            t=term, time=self.timestamp.strftime('%H:%M'), prefix=self.prefix
        )
        x = 6 + len(self.prefix)
        indent = ' ' * (x + 1)
        for word in self.text.split():
            if (x + len(word) + 1) < term.width:
                line += ' ' + word
                x += len(word) + 1
            else:
                lines.append(line)
                line = indent + word
                x = len(line)
        lines.append(line)
        return lines

    def draw(self, term, y):
        for idx, line in enumerate(reversed(self.split(term))):
            #print(y, idx, line)
            if y - idx < 0:
                return -1
            with term.location(0, y - idx):
                print(line, end='')
        return y - idx - 1


class CursesClient (NeolithClient):

    def __init__(self, loop=None):
        super().__init__(loop=loop)
        self.term = blessings.Terminal()
        self.lines = []
        self.lines.append(Line('testing ' * 30))
        self.loop.add_reader(sys.stdin, self.handle_input)
        self.loop.add_signal_handler(signal.SIGWINCH, self.redraw)

    def start(self):
        print(self.term.enter_fullscreen)
        self.redraw()

    def stop(self):
        print(self.term.exit_fullscreen)

    def handle_input(self):
        line = sys.stdin.readline().strip()
        self.lines.append(Line(line))
        self.redraw()

    def draw_lines(self):
        y = self.term.height - 3
        i = len(self.lines) - 1
        while y >= 0 and i >= 0:
            line = self.lines[i]
            y = line.draw(self.term, y)
            i -= 1

    def redraw(self):
        print(self.term.clear)
        self.draw_lines()
        status = ' [neolith] '
        if self.protocol:
            status += self.protocol.address
        else:
            status += 'NOT CONNECTED'
        remain = self.term.width - len(status)
        status += ' ' * remain
        with self.term.location(0, self.term.height - 2):
            print(self.term.bright_white_on_red(status))
        print(self.term.move(self.term.height - 1, 0), end='')

    def notify_connect(self, protocol):
        super().notify_connect(protocol)
        self.redraw()
