"""Fail-closed ClamAV INSTREAM adapter; no unscanned production file is released."""
import socket
import struct
from django.conf import settings


class ScanUnavailable(OSError):
    pass


def scan(data):
    if not settings.UPLOAD_SCAN_REQUIRED:
        return
    if not settings.UPLOAD_CLAMAV_SOCKET or len(data) > 5 * 1024 * 1024:
        raise ScanUnavailable('Private file scanning unavailable.')
    try:
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as connection:
            connection.settimeout(settings.UPLOAD_SCAN_TIMEOUT)
            connection.connect(settings.UPLOAD_CLAMAV_SOCKET)
            connection.sendall(b'zINSTREAM\0')
            for offset in range(0,len(data),65536):
                chunk=data[offset:offset+65536]
                connection.sendall(struct.pack('!I',len(chunk))+chunk)
            connection.sendall(struct.pack('!I',0))
            result=b''
            while b'\0' not in result and len(result)<1024:
                chunk=connection.recv(1024)
                if not chunk:
                    break
                result+=chunk
            if result != b'stream: OK\0':
                raise ScanUnavailable('File rejected or scanning unavailable.')
    except (OSError,ValueError):
        raise ScanUnavailable('File rejected or scanning unavailable.') from None
