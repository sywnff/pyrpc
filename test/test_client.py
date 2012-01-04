#!/usr/bin/env python
# encoding: utf-8

# Copyright 2011 Netease Inc. All Rights Reserved.
# Author: gzsyw@corp.netease.com (Shi Yanwei)

''' testing for client
'''

import sys, os
sys.path.append('../')

from pyrpc import client
import pyrpc.internal.lockservice_pb2 as lockservice_pb2

svc_host = '127.0.0.1'
svc_port = 8008

def test_channel(argv):
  import echo_service_pb2 as echo
  channel = client.ClientChannel((svc_host, svc_port))
  prx = echo.EchoService_Stub(channel)

  req = echo.EchoRequest()
  req.i = 99

  if (len(argv) > 0):
    req.i = int(argv[0])  
  
  res = prx.Echo(None, req);
  print 'res.echoed = %d' % res.echoed

  
def test_proxy(argv):
  import echo_service_pb2 as echo
  prx = client.get_proxy(echo.EchoService_Stub,
                         (svc_host, svc_port), timeout = 5.0)

  req = echo.EchoRequest()
  req.i = 99

  if (len(argv) > 0):
    req.i = int(argv[0])  

  for i in range(0, 100):
    res = prx.Echo(req);
    print 'res.echoed = %d' % res.echoed
    req.i += 1


def test_lockserver(argv):
  prx = client.get_proxy(
    lockservice_pb2.LockService_Stub,
    ('127.0.0.1', 3833),
    )
    
  req = lockservice_pb2.Request()
  req.key = "1234"
  req.value = "abc"
  res = prx.Write(req)
  print 'Write:\n', res

  req = lockservice_pb2.Request()
  req.key = "1234"
  res = prx.Read(req)
  print 'Read:\n', res
    

if __name__ == '__main__':
  import sys
  test_proxy(sys.argv[1:])
  #test_lockserver(sys.argv[1:])
