import asyncio
import logging

from core import tunnel_endpoint
from proto import Tunnel


log = logging.getLogger(__name__)


class Proxy(tunnel_endpoint.TunnelEndpoint):
    @property
    def other_endpoint(self):
        return '192.168.23.152'

    @property
    def direction(self):
        return Tunnel.Direction.to_forwarder

    async def handle_start_request(self, tunnel_packet):
        reader, writer = await asyncio.open_connection(tunnel_packet.ip, tunnel_packet.port)
        # log.debug(f'received start command. (client_id={new_icmp_packet.identifier}'
        #           f') connecting to {tunnel_packet.ip}:{tunnel_packet.port}')
        self.client_manager.add_client(
            client_id=new_icmp_packet.identifier,
            reader=reader,
            writer=writer,
        )

    async def handle_end_request(self, tunnel_packet):
        self.client_manager.remove_client(new_icmp_packet.identifier)

    async def handle_data_request(self, tunnel_packet):
        await self.client_manager.write_to_client(tunnel_packet.payload, new_icmp_packet.identifier)

    async def handle_ack_request(self, tunnel_packet):
        pass
