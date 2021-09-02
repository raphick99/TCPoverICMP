import asyncio
import logging
from exceptions import ClientClosedException


log = logging.getLogger(__name__)


class ClientSession(object):
    def __init__(self, client_id: int, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.client_id = client_id
        self.reader = reader
        self.writer = writer

    async def run(self):
        while True:
            data = await self.reader.read(1024)

            if data.decode() == '':
                log.debug(f'(client_id={self.client_id}): client disconnected. Shutting down..')
                self.writer.close()
                await self.writer.wait_closed()
                return

            log.debug(f'(client_id={self.client_id}): recv(\'{data.decode()}\')')
            # TODO send data to ICMP socket

    async def write(self, data: bytes):
        if self.writer.is_closing():
            raise ClientClosedException()

        log.debug(f'(client_id={self.client_id}): send(\'{data.decode()}\')')
        self.writer.write(data)
        await self.writer.drain()
