import asyncio
import logging
import argparse
from TCPoverICMP import proxy


logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('forwarder_ip', help='IP address of the forwarder client')
    return parser.parse_args()


async def main():
    args = parse_args()
    await proxy.Proxy(args.forwarder_ip).run()


def start_asyncio_main():
    asyncio.run(main())


if __name__ == '__main__':
    start_asyncio_main()
