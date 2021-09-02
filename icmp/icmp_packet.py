import struct
import socket

from exceptions import WrongChecksumOnICMPPacket


class ICMPPacket(object):
    ICMP_STRUCT = struct.Struct('>BBHHH')

    def __init__(self, type: int, code: int, identifier: int, sequence_number: int, payload: bytes):
        self.type = type
        self.code = code
        self.identifier = identifier
        self.sequence_number = sequence_number
        self.payload = payload

    @classmethod
    def deserialize(cls, packet: bytes):
        type, code, checksum, identifier, sequence_number = cls.ICMP_STRUCT.unpack(packet[:cls.ICMP_STRUCT.size])
        computed_checksum = cls.compute_checksum(
            cls.ICMP_STRUCT.pack(type, code, 0, identifier, sequence_number) + packet[cls.ICMP_STRUCT.size:]
        )

        if checksum != computed_checksum:
            raise WrongChecksumOnICMPPacket()

        return cls(type, code, identifier, sequence_number, packet[cls.ICMP_STRUCT.size:])

    def serialize(self):
        packet_without_checksum = self.ICMP_STRUCT.pack(
            self.type,
            self.code,
            0,
            self.identifier,
            self.sequence_number
        ) + self.payload
        checksum = self.compute_checksum(data=packet_without_checksum)

        return self.ICMP_STRUCT.pack(
            self.type,
            self.code,
            checksum,
            self.identifier,
            self.sequence_number
        ) + self.payload

    # Taken from https://github.com/Akhavi/pyping/blob/master/pyping/core.py
    @staticmethod
    def compute_checksum(data: bytes):
        count_to = (int(len(data) / 2)) * 2
        total = 0
        count = 0

        while count < count_to:
            total += int.from_bytes(data[count:count+2], byteorder='little')
            count += 2

        # Handle last byte if applicable (odd-number of bytes)
        if count_to < len(data):  # Check for odd length
            total += data[-1]

        total &= 0xffffffff  # Truncate sum to 32 bits (a variance from ping.c, which
        # uses signed ints, but overflow is unlikely in ping)

        total = (total >> 16) + (total & 0xffff)    # Add high 16 bits to low 16 bits
        total += (total >> 16)					# Add carry from above (if any)
        result = ~total & 0xffff				# Invert and truncate to 16 bits
        result = socket.htons(result)

        return result
