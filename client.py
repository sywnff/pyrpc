#!/usr/bin/env python
# encoding:utf-8

# Author: sywnff@gmail.com

''' rpc client implementation
usage:
        import pyrpc.client
        proxy = pyrpc.client.get_proxy(echo.EchoService_Stub,
                ('127.0.0.1', 8000))
        request = echo.Request()
        request.msg = 'hellow'
        respond = proxy.echo(request)
        print 'respond:%s' % respond.msg
'''

import google.protobuf.service
import socket, struct, types
import common, internal
import logging

kErr_Rpc_Channel = 300000

class ClientChannel(google.protobuf.service.RpcChannel):
  def __init__(self, svr_addr, **kvargs):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
    if 'timeout' in kvargs:
      sock.settimeout(kvargs['timeout'])
    sock.connect(svr_addr)
    self.__sock = sock
    self.__seqno = 0
    self.__delegate_sock_call()

  def CallMethod(self, method_descriptor, rpc_controller, request, response_class, done = None):
    try:
      seqno = self.SendRequest(method_descriptor, request, rpc_controller)
      respond = self.RecvResponse(response_class, seqno, rpc_controller)
    except socket.error, ex:
      logging.error('socket error:%s(%d)' % (str(ex), ex.errno))
      raise common.RpcError(kErr_Rpc_Channel, 'send/recv respond faild')
    if done != None:
      done()
    return respond

  def SendRequest(self, method_descriptor, request, rpc_controller = None):
    # request packet format:
    # content-size(4B) + seqno(8B) + hash(method_name)(8B)
    #   + serialized bytes of request message
    head_size = 20
    seqno = self.__seqno
    self.__seqno += 1

    msg_size = request.ByteSize()
    packet = struct.pack('=IQQ%ds' % msg_size, msg_size + head_size,
                         seqno, internal.hash_string(method_descriptor.full_name),
                         request.SerializeToString())
    self.__sock.send(packet)
    return seqno

  def RecvResponse(self, response_class, seqno = None, rpc_controller = None):
    # response packet format:
    # content-size(4B) + seqno(8B) +
    #   + serialized bytes of response message
    #
    head_size = 12
    buff = self.__sock.recv(head_size)
    total_size, seqno2 = struct.unpack('=IQ', buff)
    msg_bytes = self.__sock.recv(total_size - head_size)
    respond = response_class()
    if seqno and seqno2 != seqno:
      raise Exception('call sequence mismatch, expect=%d, real=%d' % (seqno, seqno2))
    
    respond.ParseFromString(msg_bytes)
    return respond

  def __delegate_sock_call(self):
    for att in ('gettimeout', 'settimeout', 'getpeername',
                'getsockname', 'getsockopt', 'setsockopt',
                ) :
      setattr(self, att, getattr(self.__sock, att))
    

class RpcClient:
  def __init__(self, svr_addr, **kvargs):
    self.__channel = ClientChannel(svr_addr, **kvargs)
    
  def get_proxy(self, service_stub_class):
    return Proxy(self, service_stub_class)
  
  def get_channel(self):
    return self.__channel

  
class Proxy:
  def __init__(self, rpc_client, service_stub_class):
    self.__channel = rpc_client.get_channel()
    self.__stub = service_stub_class(self.__channel)
    attrs = dir(self.__stub)
    for att in attrs:
      if att not in ('CallMethod', 'GetDescriptor', 'GetRequestClass', 'GetResponseClass') and \
            att[:2] != '__' and \
            type(getattr(self.__stub, att)) == types.MethodType:
        raw_func = getattr(self.__stub, att)
        setattr(self, 'raw_' + att, raw_func)
        setattr(self, att, self.__generated_new_method(att))

  def __generated_new_method(self, method_name):
    return lambda request: getattr(self, 'raw_' + method_name)(None, request)

  def get_channel(self):
    return self.__channel


def get_proxy(service_stub_class, svr_addr, **kvargs):
  rpc_client = RpcClient(svr_addr, **kvargs)
  return rpc_client.get_proxy(service_stub_class)
