import asyncio
import logging
import argparse

import proxy


logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('forwarder_ip', help='IP address of the forwarder client')
    return parser.parse_args()


async def main():
    args = parse_args()
    await proxy.Proxy(args.forwarder_ip).run()


if __name__ == '__main__':
    asyncio.run(main())
