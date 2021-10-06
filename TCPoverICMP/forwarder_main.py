import asyncio
import logging
import argparse
from TCPoverICMP import forwarder


logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('proxy_ip', help='IP address of the proxy server')
    parser.add_argument('listening_port', type=int, help='Port on which the forwarder will listen')
    parser.add_argument('destination_ip', help='IP address to forward to')
    parser.add_argument('destination_port', type=int, help='port to forward to')
    return parser.parse_args()


async def main():
    args = parse_args()
    await forwarder.Forwarder(args.proxy_ip, args.listening_port, args.destination_ip, args.destination_port).run()


def start_asyncio_main():
    asyncio.run(main())


if __name__ == '__main__':
    start_asyncio_main()
