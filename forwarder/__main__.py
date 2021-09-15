import asyncio
import logging
import argparse

import forwarder


logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('proxy_ip', help='IP address of the proxy server')
    parser.add_argument('listening_port', type=int, help='Port on which the forwarder will listen on')
    parser.add_argument('destination_ip', help='IP address to forward to')
    parser.add_argument('destination_port', help='port to forward to')
    return parser.parse_args()


async def main():
    args = parse_args()
    await forwarder.Forwarder(args.proxy_ip, args.listening_port, args.destination_ip, args.destination_port).run()


if __name__ == '__main__':
    asyncio.run(main())
