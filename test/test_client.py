#!/usr/bin/env python
# encoding: utf-8

# Author: sywnff@gmail.com

''' testing for client
'''

import sys, os
sys.path.append('../')

from pyrpc import client

svc_host = '127.0.0.1'
svc_port = 8008

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


if __name__ == '__main__':
  import sys
  test_proxy(sys.argv[1:])

