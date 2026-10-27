"""Disposable loopback TLS fixture. Invented candles; never logs request headers."""
import os
from pathlib import Path
import socket
import ssl
import subprocess
import threading
from urllib.parse import parse_qsl,urlsplit
from .oneshot import SPEC
from .oneshot_archive import FIXTURES,Refused
from .oanda_history_manifest import encoded
from .history_fixtures import payload
from .core import timestamp


def openssl_program():
    return r'C:\Program Files\Git\usr\bin\openssl.exe' if os.name=='nt' else '/usr/bin/openssl'


def certificate(directory):
    """Ephemeral unencrypted *test* key only; no key bytes enter source/logs."""
    global CERT_ARGV
    directory=Path(directory)
    if not directory.resolve().is_relative_to(FIXTURES):raise Refused('CERTIFICATE_FIXTURE_ROOT_REQUIRED')
    directory.mkdir()
    config=directory/'openssl.cnf';key=directory/'key.pem';cert=directory/'cert.pem'
    config.write_text('[req]\ndistinguished_name=dn\n[dn]\nCN=localhost\n',encoding='ascii')
    argv=[openssl_program(),'req','-x509','-newkey','ec','-pkeyopt','ec_paramgen_curve:P-256',
          '-nodes','-days','1','-subj','/CN=localhost','-addext','subjectAltName=DNS:localhost,IP:127.0.0.1',
          '-config',str(config),'-keyout',str(key),'-out',str(cert)]
    CERT_ARGV=argv
    subprocess.run(argv,check=True,timeout=5,env={},stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    if os.name!='nt':key.chmod(0o600)
    return cert,key


class LocalHTTPS:
    def __init__(self,cert,key,*,scenario='valid',secret):
        self.context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);self.context.load_cert_chain(cert,key)
        self.cert=Path(cert).read_text(encoding='ascii');self.scenario=scenario;self.secret=secret
        self.stop=threading.Event();self.phase=threading.Event();self.ready=threading.Event()
        self.connections=0;self.requests=[];self.errors=[];self.listener=None;self.active=None
        self.port=None;self.thread=None

    def __enter__(self):
        self.listener=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        self.listener.bind(('127.0.0.1',0));self.port=self.listener.getsockname()[1]
        if self.scenario=='connection_refused':return self # bound, not listening; prevents port reuse
        self.listener.listen(4);self.listener.settimeout(.1)
        self.thread=threading.Thread(target=self.serve,daemon=True);self.thread.start()
        if not self.ready.wait(2):raise RuntimeError('FIXTURE_STARTUP_FAILED')
        return self

    def binding(self,verification='trusted'):
        return {'port':self.port,'certificate':self.cert,'verification':verification}

    def serve(self):
        self.ready.set()
        while not self.stop.is_set():
            try:conn,_=self.listener.accept()
            except TimeoutError:continue
            except OSError:break
            self.connections+=1;self.active=conn
            try:
                conn.settimeout(2)
                if self.scenario=='delayed_tls':self.phase.set();self.stop.wait(10);continue
                conn=self.context.wrap_socket(conn,server_side=True);self.active=conn
                raw=b''
                while b'\r\n\r\n' not in raw:
                    block=conn.recv(1024)
                    if not block:raise ValueError()
                    raw+=block
                    if len(raw)>4096:raise ValueError()
                lines=raw.decode('ascii').split('\r\n');method,target,_=lines[0].split(' ')
                headers=dict(line.split(': ',1) for line in lines[1:] if ': ' in line)
                parsed=urlsplit(target);params=dict(parse_qsl(parsed.query,strict_parsing=True))
                valid=method=='GET' and parsed.path==SPEC['path'] and params==SPEC['params']
                auth=headers.get('Authorization')=='Bearer '+self.secret
                self.requests.append({'method':method,'path':parsed.path,'scope_valid':valid,'auth_matches':auth})
                if not valid or not auth:raise ValueError()
                self.phase.set()
                if self.scenario=='delayed_headers':self.stop.wait(10);continue
                begin=timestamp(SPEC['params']['from'])
                obj=payload(start=begin,count=9 if self.scenario=='nine' else 10)
                if self.scenario=='invalid_schema':obj['instrument']='GBP_USD'
                if self.scenario=='incomplete_candles':obj['candles'][-1]['complete']=False
                if self.scenario=='credential_echo':obj['echo']=self.secret
                body=b'{bad' if self.scenario=='malformed' else encoded(obj)
                if self.scenario=='oversized_stream':body=b'x'*(8*1024*1024+1)
                status=int(self.scenario[5:]) if self.scenario.startswith('http_') else 302 if self.scenario=='redirect' else 200
                if status!=200:body=b'fixture error'
                declared=len(body)+10 if self.scenario=='incomplete_body' else 8*1024*1024+1 if self.scenario=='oversized' else len(body)
                extra='Location: https://api-fxtrade.oanda.com/forbidden\r\n' if status==302 else ''
                length='' if self.scenario=='oversized_stream' else f'Content-Length: {declared}\r\n'
                header=f'HTTP/1.1 {status} Fixture\r\nContent-Type: application/json\r\n{length}Connection: close\r\n{extra}\r\n'.encode('ascii')
                conn.sendall(header)
                if self.scenario=='slow_body':
                    for value in body:
                        if self.stop.wait(.05):break
                        conn.sendall(bytes([value]))
                else:conn.sendall(body)
            except (OSError,ValueError):
                # TLS rejection, reset/EOF and fixture teardown are expected.
                self.errors.append('FIXTURE_CONNECTION_CLOSED')
            finally:
                conn.close();self.active=None

    def __exit__(self,*_):
        self.stop.set()
        if self.active is not None:
            try:self.active.shutdown(socket.SHUT_RDWR)
            except OSError:pass
        self.listener.close()
        if self.thread:
            self.thread.join(2)
            if self.thread.is_alive():raise RuntimeError('FIXTURE_SHUTDOWN_FAILED')
