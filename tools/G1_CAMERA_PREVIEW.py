"""Standalone camera browser preview: no Unity, IK, Omni, PTZ or motor owner."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import secrets
import socket
import threading
import time
import webbrowser

from g1_camera_h264 import run
from g1_camera_ssh import HEADER, read_packet
from g1_portable_environment import select_robot_host


def serve(host, open_browser=True, seconds=0):
    stopped = threading.Event()
    changed = threading.Condition()
    state = dict(frame=None,sequence=-1,count=0,last=0.,error=None)
    token = secrets.token_urlsafe(24)
    listener = socket.socket()
    if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
        listener.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
    listener.bind(('127.0.0.1',0))
    listener.listen(1)
    listener.settimeout(.5)
    address = listener.getsockname()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass

        def reply(self,data,content_type,code=200):
            self.send_response(code)
            self.send_header('Content-Type',content_type)
            self.send_header('Cache-Control','no-store')
            self.send_header('Content-Length',str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            try:
                if self.path=='/':
                    html='''<!doctype html><meta charset="utf-8"><title>G1 Camera Only</title>
<style>body{margin:0;background:#15191e;color:#eee;font:16px sans-serif;text-align:center}
header{padding:14px}button{margin-left:20px;padding:10px 24px;cursor:pointer}
img{width:min(100vw,1400px);max-height:82vh;object-fit:contain}#status{padding:8px}</style>
<header>G1 카메라만 보기 · 1920×1080 / 30fps · H.264
<button onclick="stopCamera()">카메라 종료</button></header>
<div id="status">카메라 연결 중…</div><img id="video" src="/stream">
<p>Unity · IK · Omni · 로봇 모터 제어는 실행하지 않습니다.<br>
탭만 닫으면 수신은 계속됩니다. 종료 버튼 또는 실행 창의 Ctrl+C로 종료하세요.</p>
<script>async function stopCamera(){await fetch('/stop/TOKEN',{method:'POST'});
document.getElementById('video').src='';document.getElementById('status').textContent='카메라 종료됨';clearInterval(timer)}
const timer=setInterval(async()=>{try{let s=await(await fetch('/status')).json();
document.getElementById('status').textContent=s.error||
(s.age_s===null?'첫 영상 대기':(s.age_s>1?'영상 수신 지연':'영상 수신 중')+' · '+s.count+' frames · '+s.age_s.toFixed(2)+'s ago')}
catch(e){}},1000);</script>'''.replace('TOKEN',token)
                    self.reply(html.encode('utf-8'),'text/html; charset=utf-8')
                elif self.path=='/status':
                    with changed:
                        data=dict(count=state['count'],error=state['error'],
                            age_s=time.monotonic()-state['last'] if state['last'] else None)
                    self.reply(json.dumps(data).encode(),'application/json')
                elif self.path=='/stream':
                    self.connection.settimeout(2)
                    self.send_response(200)
                    self.send_header('Content-Type','multipart/x-mixed-replace; boundary=frame')
                    self.send_header('Cache-Control','no-store');self.end_headers()
                    previous=-1
                    while not stopped.is_set():
                        with changed:
                            changed.wait_for(lambda:state['sequence']!=previous or stopped.is_set(),timeout=1)
                            if stopped.is_set():break
                            if state['sequence']==previous or state['frame'] is None:continue
                            previous=state['sequence'];frame=state['frame']
                        self.wfile.write(b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: '+
                            str(len(frame)).encode()+b'\r\n\r\n'+frame+b'\r\n');self.wfile.flush()
                else:self.reply(b'Not found','text/plain',404)
            except (OSError,ConnectionError):pass

        def do_POST(self):
            if self.path!='/stop/'+token:
                self.reply(b'Forbidden','text/plain',403);return
            self.reply(b'Stopping','text/plain');stopped.set()

    http = ThreadingHTTPServer(('127.0.0.1',0),Handler)
    http.daemon_threads = True
    url='http://127.0.0.1:%d/'%http.server_port

    def receive():
        try:
            while not stopped.is_set():
                try:conn,_=listener.accept()
                except socket.timeout:continue
                conn.settimeout(5)
                with conn,conn.makefile('rb') as stream:
                    while not stopped.is_set():
                        packet=read_packet(stream)
                        seq=HEADER.unpack(packet[:HEADER.size])[2]
                        with changed:
                            state.update(frame=packet[HEADER.size:],sequence=seq,
                                count=state['count']+1,last=time.monotonic())
                            changed.notify_all()
                break
        except Exception as error:
            if not stopped.is_set():
                with changed:state['error']='Camera receive: '+str(error)

    def camera():
        try:run(host,output_address=address,stop_event=stopped)
        except Exception as error:
            with changed:state['error']='Camera: '+str(error)
            print(state['error'],flush=True)
        finally:
            if state['error']:stopped.set()

    receiver=threading.Thread(target=receive,daemon=True)
    capture=threading.Thread(target=camera,daemon=True)
    browser=threading.Thread(target=http.serve_forever,daemon=True)
    try:
        receiver.start();browser.start();capture.start()
        print('CAMERA ONLY PREVIEW: '+url,flush=True)
        print('Stop: page button or Ctrl+C. No Unity, PTZ or motor program.',flush=True)
        if open_browser:webbrowser.open(url)
        deadline=time.monotonic()+seconds if seconds else float('inf')
        while not stopped.wait(.2) and time.monotonic()<deadline:pass
    except KeyboardInterrupt:pass
    finally:
        stopped.set()
        with changed:changed.notify_all()
        capture.join(12)
        http.shutdown();http.server_close();listener.close();receiver.join(6)
        print('CAMERA PREVIEW STOPPED. frames=%d'%state['count'],flush=True)
    return 1 if state['error'] or capture.is_alive() else 0


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host',default='auto')
    parser.add_argument('--no-browser',action='store_true')
    parser.add_argument('--seconds',type=int,default=0,help='Optional bounded camera-only test, 1..300s')
    args=parser.parse_args(argv)
    if not 0<=args.seconds<=300:parser.error('seconds must be 0..300')
    return serve(select_robot_host(args.host),not args.no_browser,args.seconds)


if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,RuntimeError,ValueError) as error:
        print('CAMERA PREVIEW: '+str(error),flush=True);raise SystemExit(1)
