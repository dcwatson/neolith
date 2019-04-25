from .curses import CursesClient

import argparse
import asyncio
import importlib
import logging.config
import os
import sys


def init():
    print('Initializing neolith server configs in {}'.format(os.getcwd()))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", dest='port', default=8120, help="The port to connect on.")
    parser.add_argument('host', nargs='?', default='127.0.0.1')
    args = parser.parse_args()

    loop = asyncio.get_event_loop()
    client = CursesClient(loop=loop)
    client.start()
    client.connect()  # move this to /connect

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        client.stop()
        loop.close()

    return 0


if __name__ == '__main__':
    sys.exit(main())
