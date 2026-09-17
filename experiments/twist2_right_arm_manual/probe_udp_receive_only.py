"""Run via SSH stdin with python3 -B; no robot files, SDK, or packet output."""
import hashlib
import json
import socket
import time

def main():
    count=0
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as receiver:
        # Exclusive bind; never displace another receiver or set SO_REUSEADDR.
        receiver.bind(('192.168.123.164',5013))
        receiver.settimeout(1)
        print(json.dumps(dict(event='ready',port=5013,command_output=False)),flush=True)
        deadline=time.monotonic()+60
        while count<3 and time.monotonic()<deadline:
            try:packet,source=receiver.recvfrom(16385)
            except socket.timeout:continue
            value=json.loads(packet)
            if source[0]!='192.168.123.99' or value.get('schema')!='twist2.transport_probe.no_command.v1':
                raise ValueError('unexpected source or probe schema')
            if value.get('sequence')!=count or set(value)!={'schema','sequence','padding'}:
                raise ValueError('unexpected probe fields or sequence')
            print(json.dumps(dict(event='received',sequence=count,source=source,
                bytes=len(packet),sha256=hashlib.sha256(packet).hexdigest())),flush=True)
            count+=1
    print(json.dumps(dict(event='end',received=count,command_output=False)),flush=True)
    return 0 if count==3 else 1

if __name__=='__main__':raise SystemExit(main())
