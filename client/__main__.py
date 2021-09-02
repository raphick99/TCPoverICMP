import asyncio
import logging
from server import Server


logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)


async def main(host: str, port: int):
    tcp_server = Server(host, port)
    await tcp_server.serve_forever()


if __name__ == '__main__':
    asyncio.run(main('127.0.0.1', 13337))
