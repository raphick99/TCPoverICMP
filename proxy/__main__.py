import asyncio
import logging

import proxy


logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)


async def main():
    await proxy.Proxy().run()


if __name__ == '__main__':
    asyncio.run(main())
