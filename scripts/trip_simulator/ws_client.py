"""Cliente WebSocket RFC 6455 enxuto em stdlib Python (sem novas dependências)."""

import base64
import contextlib
import hashlib
import os
import socket
import struct
from urllib.parse import urlsplit


class SimpleWebSocketClient:
    """Cliente síncrono minimalista para enviar/receber frames JSON sobre WS/HTTP local."""

    def __init__(self, url: str, *, origin: str, cookie_header: str, timeout: float = 10.0):
        self.url = url
        self.origin = origin
        self.cookie_header = cookie_header
        self.timeout = timeout
        self._sock: socket.socket | None = None

    def connect(self):
        parsed = urlsplit(self.url)
        if parsed.scheme != 'ws':
            raise ValueError('O simulador local suporta apenas ws://.')
        host = parsed.hostname or '127.0.0.1'
        port = parsed.port or 80
        path = parsed.path or '/'
        if parsed.query:
            path = f'{path}?{parsed.query}'

        key = base64.b64encode(os.urandom(16)).decode('ascii')
        expected_accept = base64.b64encode(
            hashlib.sha1(f'{key}258EAFA5-E914-47DA-95CA-C5AB0DC85B11'.encode('ascii')).digest()
        ).decode('ascii')

        sock = socket.create_connection((host, port), timeout=self.timeout)
        request_lines = [
            f'GET {path} HTTP/1.1',
            f'Host: {host}:{port}',
            'Upgrade: websocket',
            'Connection: Upgrade',
            f'Sec-WebSocket-Key: {key}',
            'Sec-WebSocket-Version: 13',
            f'Origin: {self.origin}',
            f'Cookie: {self.cookie_header}',
            '',
            '',
        ]
        sock.sendall('\r\n'.join(request_lines).encode('utf-8'))

        response = b''
        while b'\r\n\r\n' not in response:
            chunk = sock.recv(4096)
            if not chunk:
                sock.close()
                raise ConnectionError('Conexão encerrada durante handshake WebSocket.')
            response += chunk

        header_block = response.split(b'\r\n\r\n', 1)[0].decode('latin1')
        status_line = header_block.splitlines()[0]
        if '101' not in status_line:
            sock.close()
            raise ConnectionError(f'Handshake WebSocket recusado: {status_line}')
        if expected_accept not in header_block:
            sock.close()
            raise ConnectionError('Sec-WebSocket-Accept inválido no handshake.')

        self._sock = sock

    def send_text(self, text: str):
        if self._sock is None:
            raise ConnectionError('WebSocket não conectado.')
        self._send_frame(0x1, text.encode('utf-8'))

    def close(self):
        if self._sock is None:
            return
        try:
            with contextlib.suppress(OSError):
                self._send_frame(0x8, b'')
        finally:
            with contextlib.suppress(OSError):
                self._sock.close()
            self._sock = None

    def _send_frame(self, opcode: int, payload: bytes):
        if self._sock is None:
            return
        mask_key = os.urandom(4)
        length = len(payload)
        header = bytearray([0x80 | opcode])
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header.extend(struct.pack('!H', length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack('!Q', length))
        header.extend(mask_key)
        masked = bytes(byte ^ mask_key[idx % 4] for idx, byte in enumerate(payload))
        self._sock.sendall(bytes(header) + masked)
