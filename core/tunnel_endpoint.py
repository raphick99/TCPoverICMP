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
        self.coroutines_to_run.append(self.wait_for_stale_connection())

    @property
    def other_endpoint(self):
        return '0.0.0.0'

    async def run(self):
        constant_coroutines = [
            self.icmp_socket.wait_for_incoming_packet(),
        ]
        running_tasks = [asyncio.create_task(coroutine) for coroutine in self.coroutines_to_run + constant_coroutines]

        await asyncio.gather(*running_tasks)

    async def wait_for_stale_connection(self):
        while True:
            client_id = await self.stale_tcp_connections.get()

            new_tunnel_packet = Tunnel(
                ip='',
                port=0,
                state=Tunnel.State.end,
                direction=Tunnel.Direction.to_proxy,
                payload=b'',
            )

            new_icmp_packet = icmp_packet.ICMPPacket(
                type=icmp_packet.ICMPType.EchoRequest,
                identifier=client_id,
                sequence_number=0,
                payload=new_tunnel_packet.SerializeToString(),
            )
            self.icmp_socket.sendto(new_icmp_packet)

            self.client_manager.remove_client(client_id)
