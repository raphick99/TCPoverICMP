import asyncio
import logging

import forwarder


logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)


async def main(host: str, port: int):
    await forwarder.Forwarder(host, port, '192.168.23.153', 8080).run()


if __name__ == '__main__':
    asyncio.run(main('0.0.0.0', 13337))
