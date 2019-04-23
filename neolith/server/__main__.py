from .base import NeolithServer

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
    parser.add_argument("--config", default="config", help="The configuration module to load.")
    parser.add_argument("command", nargs='?', choices=["init"])
    args = parser.parse_args()

    if args.command == 'init':
        return init()

    try:
        local_config = importlib.import_module(args.config)
        # settings.update(local_config)
    except ImportError:
        pass

    # logging.config.dictConfig(settings.LOGGING)

    loop = asyncio.get_event_loop()
    server = NeolithServer(loop=loop)
    server.start()

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()

    return 0


if __name__ == '__main__':
    sys.exit(main())
