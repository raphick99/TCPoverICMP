import asyncio
import logging

from core import tunnel_endpoint
from tcp import server
from icmp import icmp_packet
from proto import Tunnel


log = logging.getLogger(__name__)


class Forwarder(tunnel_endpoint.TunnelEndpoint):
    def __init__(self, host, port, destination_host, destination_port):
        super(Forwarder, self).__init__()
        log.info(f'forwarding to {destination_host}:{destination_port}')
        self.destination_host = destination_host
        self.destination_port = destination_port
        self.incoming_tcp_connections = asyncio.Queue(maxsize=1000)
        self.tcp_server = server.Server(host, port, self.incoming_tcp_connections)
        self.coroutines_to_run.append(self.tcp_server.serve_forever())
        self.coroutines_to_run.append(self.wait_for_new_connection())

    @property
    def other_endpoint(self):
        return '192.168.23.153'

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
        await self.client_manager.write_to_client(tunnel_packet.payload, tunnel_packet.client_id)
        self.send_ack(tunnel_packet)

    async def handle_ack_request(self, tunnel_packet: Tunnel):
        pass

    async def wait_for_new_connection(self):
        while True:
            client_id, reader, writer = await self.incoming_tcp_connections.get()

            new_tunnel_packet = Tunnel(
                client_id=client_id,
                sequence_number=0,
                action=Tunnel.Action.start,
                direction=self.direction,
                ip=self.destination_host,
                port=self.destination_port,
            )
            self.send_icmp_packet(icmp_packet.ICMPType.EchoRequest, new_tunnel_packet.SerializeToString())
            self.client_manager.add_client(client_id, reader, writer)
