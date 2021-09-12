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
        self.coroutines_to_run.append(self.wait_for_new_connection())

    @property
    def other_endpoint(self):
        return '192.168.23.153'

    @property
    def direction(self):
        return Tunnel.Direction.to_proxy

    def handle_start_request(self, tunnel_packet):
        log.debug('invalid start command. ignoring')

    def handle_end_request(self, tunnel_packet):
        self.client_manager.remove_client(tunnel_packet.identifier)

    def handle_data_request(self, tunnel_packet):
        # await self.client_manager.write_to_client(tunnel_packet.payload, new_icmp_packet.identifier)
        pass

    def handle_ack_request(self, tunnel_packet):
        pass

    async def wait_for_new_connection(self):
        while True:
            client_id, reader, writer = await self.incoming_tcp_connections.get()

            new_tunnel_packet = Tunnel(
                ip=self.destination_host,
                port=self.destination_port,
                action=Tunnel.Action.start,
                direction=Tunnel.Direction.to_proxy,
                payload=b'',
            )
            self.send_icmp_packet(icmp_packet.ICMPType.EchoRequest, client_id, 0, new_tunnel_packet.SerializeToString())
            self.client_manager.add_client(client_id, reader, writer)
