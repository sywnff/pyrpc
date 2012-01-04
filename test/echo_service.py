# encoding: utf-8

# Copyright 2011 Netease Inc. All Rights Reserved.
# Author: gzsyw@corp.netease.com (Shi Yanwei)

''' deom: echo service implementation
'''

import echo_service_pb2

class EchoService(echo_service_pb2.EchoService):
  def Echo(self, request, seqno, channel, **kvargs):
    print 'Echo: %d' % request.i
    print 'remote address:%s' % str(channel.remote_addr)
    respond = echo_service_pb2.EchoResponse()
    respond.echoed = request.i + 1
    # if no return, NO response packet send to caller,
    # you can use channel.send_response_msg(msg, seqno) later
    return respond
