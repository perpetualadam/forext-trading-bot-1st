"""Invented candles and virtual HTTP time. Never market evidence."""
import json
import threading
from .core import timestamp,iso
from .oanda_history_transport import Response,CandleTransport

T=timestamp('2024-01-01T00:00:00Z')


def payload(pair='EUR_USD',start=T,count=3,*,empty=False):
    candles=[]
    base=150 if pair=='USD_JPY' else 1.1
    for i in range(0 if empty else count):
        c=dict(time=iso(start+i*300),complete=True,volume=1)
        for name,shift in [('mid',0),('bid',-.0001),('ask',.0001)]:
            c[name]={k:format(base+shift+v,'.5f') for k,v in [('o',0),('h',.0002),('l',-.0002),('c',0)]}
        candles.append(c)
    return dict(instrument=pair,granularity='M5',candles=candles)


class Virtual:
    def __init__(self,responses=None):
        self.responses=list(responses or []);self.calls=[];self.waits=[];self.now=0.0
    def clock(self): return self.now
    def wait(self,seconds): self.waits.append(seconds);self.now+=seconds;return False
    def sender(self,method,host,path,params):
        self.calls.append((method,host,path,params))
        if self.responses:
            r=self.responses.pop(0)
            if isinstance(r,BaseException): raise r
            return r
        start=timestamp(params['from']);end=timestamp(params['to'])+1
        return Response(200,json.dumps(payload(path.split('/')[3],start,(end-start)//300)).encode())
    def transport(self,**kwargs):
        return CandleTransport(sender=self.sender,clock=self.clock,wait=self.wait,wall=lambda:T+86400,**kwargs)
