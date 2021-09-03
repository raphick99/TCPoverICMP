import asyncio
import logging

import forwarder


logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)


async def main(host: str, port: int):
    f = forwarder.Forwarder(host, port)
    await f.start()


if __name__ == '__main__':
    asyncio.run(main('127.0.0.1', 13337))
