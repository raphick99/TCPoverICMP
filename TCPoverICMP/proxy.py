import asyncio
import logging
from TCPoverICMP import tunnel_endpoint
from TCPoverICMP.proto import Tunnel


log = logging.getLogger(__name__)


class Proxy(tunnel_endpoint.TunnelEndpoint):
    @property
    def direction(self):
        return Tunnel.Direction.to_forwarder

    async def handle_start_request(self, tunnel_packet: Tunnel):
        try:
            reader, writer = await asyncio.open_connection(tunnel_packet.ip, tunnel_packet.port)
        except ConnectionRefusedError:
            log.debug(f'{tunnel_packet.ip}:{tunnel_packet.port} refused connection. tunnel not started.')
            return

        self.client_manager.add_client(
            client_id=tunnel_packet.client_id,
            reader=reader,
            writer=writer,
        )
        self.send_ack(tunnel_packet)
