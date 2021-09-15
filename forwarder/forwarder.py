import asyncio
import logging

from core import tunnel_endpoint
from tcp import server
from icmp import icmp_packet
from proto import Tunnel


log = logging.getLogger(__name__)


class Forwarder(tunnel_endpoint.TunnelEndpoint):
    def __init__(self, other_endpoint, host, port, destination_host, destination_port):
        super(Forwarder, self).__init__(other_endpoint)
        log.info(f'forwarding to {destination_host}:{destination_port}')
        self.destination_host = destination_host
        self.destination_port = destination_port
        self.incoming_tcp_connections = asyncio.Queue(maxsize=1000)
        self.tcp_server = server.Server(host, port, self.incoming_tcp_connections)
        self.coroutines_to_run.append(self.tcp_server.serve_forever())
        self.coroutines_to_run.append(self.wait_for_new_connection())

    @property
    def direction(self):
        return Tunnel.Direction.to_proxy

    async def handle_start_request(self, tunnel_packet: Tunnel):
        log.debug('invalid start command. ignoring')
        self.send_ack(tunnel_packet)

    async def handle_end_request(self, tunnel_packet: Tunnel):
        await self.client_manager.remove_client(tunnel_packet.client_id)
        self.send_ack(tunnel_packet)

    async def handle_data_request(self, tunnel_packet: Tunnel):
        await self.client_manager.write_to_client(
            tunnel_packet.client_id,
            tunnel_packet.sequence_number,
            tunnel_packet.payload
        )
        self.send_ack(tunnel_packet)

    async def handle_ack_request(self, tunnel_packet: Tunnel):
        self.packets_requiring_ack[(tunnel_packet.client_id, tunnel_packet.sequence_number)].set()

    async def wait_for_new_connection(self):
        while True:
            client_id, reader, writer = await self.incoming_tcp_connections.get()

            new_tunnel_packet = Tunnel(
                client_id=client_id,
                action=Tunnel.Action.start,
                direction=self.direction,
                ip=self.destination_host,
                port=self.destination_port,
            )
            await self.send_icmp_packet_and_wait_for_ack(new_tunnel_packet)
            self.client_manager.add_client(client_id, reader, writer)
