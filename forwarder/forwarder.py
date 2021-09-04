import asyncio
import logging

import server
from icmp import icmp_socket, icmp_packet


log = logging.getLogger(__name__)


class Forwarder(object):
    def __init__(self, host, port):
        self.incoming_from_icmp_channel = asyncio.Queue(maxsize=0x64)
        self.incoming_from_tcp_channel = asyncio.Queue(maxsize=0x100)
        self.icmp_socket = icmp_socket.ICMPSocket(
            self.incoming_from_icmp_channel, '127.0.0.1'  # TODO have the endpoint be configurable
        )
        self.tcp_server = server.Server(host, port, self.incoming_from_tcp_channel)

    async def run(self):
        await asyncio.gather(
            asyncio.create_task(self.handle_incoming_from_icmp_channel()),
            asyncio.create_task(self.handle_incoming_from_tcp_channel()),
            asyncio.create_task(self.icmp_socket.wait_for_incoming_packet()),
            asyncio.create_task(self.tcp_server.serve_forever()),
        )

    async def handle_incoming_from_icmp_channel(self):
        while True:
            new_icmp_packet = await self.incoming_from_icmp_channel.get()
            log.debug(f'received new packet from icmp. writing to client.')
            await self.tcp_server.write_to_client(new_icmp_packet.payload, new_icmp_packet.identifier)

    async def handle_incoming_from_tcp_channel(self):
        while True:
            data, client_id, seq_num = await self.incoming_from_tcp_channel.get()
            log.debug(f'received from tcp channel: {data}, client_id: {client_id}, seq_num: {seq_num}')
            new_icmp_packet = icmp_packet.ICMPPacket(
                type=icmp_packet.ICMPType.EchoRequest,
                identifier=client_id,
                sequence_number=seq_num,
                payload=data,
            )
            self.icmp_socket.sendto(new_icmp_packet)
