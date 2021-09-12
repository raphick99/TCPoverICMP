import asyncio
import logging

from tcp import client_manager
from icmp import icmp_socket, icmp_packet
from proto import Tunnel


log = logging.getLogger(__name__)


def consume_queue(queue_to_consume):
    def wrap_function(f):
        async def wrapper(*_, **__):
            while True:
                args = await queue_to_consume.get()
                await f(*args)
        return wrapper
    return wrap_function


class TunnelEndpoint:
    def __init__(self):
        self.stale_tcp_connections = asyncio.Queue(maxsize=1000)
        self.incoming_from_icmp_channel = asyncio.Queue(maxsize=1000)
        self.incoming_from_tcp_channel = asyncio.Queue(maxsize=1000)
        self.icmp_socket = icmp_socket.ICMPSocket(
            self.incoming_from_icmp_channel, self.other_endpoint  # TODO have the endpoint be configurable
        )

        self.client_manager = client_manager.ClientManager(
            self.stale_tcp_connections,
            self.incoming_from_tcp_channel
        )

        self.coroutines_to_run = []

    @property
    def other_endpoint(self):
        raise NotImplementedError()

    @property
    def direction(self):
        raise NotImplementedError()

    async def run(self):
        constant_coroutines = [
            self.wait_for_stale_connection(),
            self.handle_incoming_from_tcp_channel(),
            self.icmp_socket.wait_for_incoming_packet(),
        ]
        running_tasks = [asyncio.create_task(coroutine) for coroutine in self.coroutines_to_run + constant_coroutines]

        await asyncio.gather(*running_tasks)

    async def handle_incoming_from_tcp_channel(self):
        while True:
            data, client_id, seq_num = await self.incoming_from_tcp_channel.get()

            new_tunnel_packet = Tunnel(
                ip='',
                port=0,
                state=Tunnel.State.data,
                direction=self.direction,
                payload=data,
            )
            self.send_icmp_packet(icmp_packet.ICMPType.EchoRequest, client_id, seq_num, new_tunnel_packet.SerializeToString())

    async def wait_for_stale_connection(self):
        while True:
            client_id = await self.stale_tcp_connections.get()

            new_tunnel_packet = Tunnel(
                ip='',
                port=0,
                state=Tunnel.State.end,
                direction=self.direction,
                payload=b'',
            )

            self.send_icmp_packet(icmp_packet.ICMPType.EchoRequest, client_id, 0, new_tunnel_packet.SerializeToString())
            self.client_manager.remove_client(client_id)

    def send_icmp_packet(
            self,
            type: icmp_packet.ICMPType,
            identifier: int,
            sequence_number: int,
            payload: bytes
    ):
        new_icmp_packet = icmp_packet.ICMPPacket(
            type=type,
            identifier=identifier,
            sequence_number=sequence_number,
            payload=payload
        )
        self.icmp_socket.sendto(new_icmp_packet, self.other_endpoint)
