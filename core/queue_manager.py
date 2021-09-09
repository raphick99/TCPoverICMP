import asyncio
import logging

from tcp import client_manager
from icmp import icmp_socket, icmp_packet


log = logging.getLogger(__name__)


class QueueManager:
    def __init__(self):
        self.incoming_tcp_connections = asyncio.Queue(maxsize=1000)
        self.stale_tcp_connections = asyncio.Queue(maxsize=1000)
        self.incoming_from_icmp_channel = asyncio.Queue(maxsize=1000)
        self.incoming_from_tcp_channel = asyncio.Queue(maxsize=1000)
        self.icmp_socket = icmp_socket.ICMPSocket(
            self.incoming_from_icmp_channel, '0.0.0.0'  # TODO have the endpoint be configurable
        )
        self.client_manager = client_manager.ClientManager(
            self.incoming_tcp_connections,
            self.stale_tcp_connections,
            self.incoming_from_tcp_channel
        )

        self.coroutines_to_run = []

    async def run(self):
        constant_coroutines = [
            self.handle_incoming_from_icmp_channel(),
            self.handle_incoming_from_tcp_channel(),
            self.icmp_socket.wait_for_incoming_packet(),
            self.client_manager.wait_for_new_connection(),
            self.client_manager.wait_for_stale_connection(),
        ]
        running_tasks = [asyncio.create_task(coroutine) for coroutine in self.coroutines_to_run + constant_coroutines]

        await asyncio.gather(*running_tasks)

    async def handle_incoming_from_icmp_channel(self):
        while True:
            new_icmp_packet = await self.incoming_from_icmp_channel.get()
            # log.debug(f'received new packet from icmp. writing to client.')
            await self.client_manager.write_to_client(new_icmp_packet.payload, new_icmp_packet.identifier)

    async def handle_incoming_from_tcp_channel(self):
        while True:
            data, client_id, seq_num = await self.incoming_from_tcp_channel.get()
            # log.debug(f'received from tcp channel: {data}, client_id: {client_id}, seq_num: {seq_num}')
            new_icmp_packet = icmp_packet.ICMPPacket(
                type=icmp_packet.ICMPType.EchoRequest,
                identifier=client_id,
                sequence_number=seq_num,
                payload=data,
            )
            self.icmp_socket.sendto(new_icmp_packet)
