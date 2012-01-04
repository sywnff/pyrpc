#!/usr/bin/env python
# encoding:utf-8

# Copyright 2011 Netease Inc. All Rights Reserved.
# Author: gzsyw@corp.netease.com (Shi Yanwei)

''' rpc server side
'''

import socket, struct, types, select, UserString
import google.protobuf.service
import logging, errno, threading
import internal

from select import EPOLLERR, EPOLLET, EPOLLHUP, EPOLLIN,\
    EPOLLOUT, EPOLLPRI

NORMAL_POLL_MASK = EPOLLERR | EPOLLHUP | EPOLLIN | EPOLLPRI

def _check_true(flag, fun = None):
  if fun and fun():
    return True
  return flag


class Dispatcher:
  def __init__(self, halt_notify = None, **kvargs):
    self.__epfd = select.epoll()
    self.__handlers = {}
    self.__halt_notify = halt_notify
    self.__halt = False
    self.__obj_manager = None

  def set_handler(self, fd, handler, mask = NORMAL_POLL_MASK):
    if fd in self.__handlers:
      self.__epfd.modify(fd, mask)
    else:
      self.__epfd.register(fd, mask)
    self.__handlers[fd] = handler

  def remove_handler(self, fd):
    self.__epfd.unregister(fd)
    if self.__handlers.has_key(fd):
      self.__handlers.pop(fd)

  def modify_handler(self, fd, mask):
    if self.__handlers.has_key(fd):
      self.__epfd.modify(fd, mask)

  def set_object_manager(self, obj_manager):
    self.__obj_manager = obj_manager

  def get_object_manager(self):
    return self.__obj_manager
  
  def loop(self, timeout = -1):
    while not _check_true(self.__halt, self.__halt_notify):
      try:
        events = self.__epfd.poll(timeout)
        if events != []:
          logging.debug('epoll events: %s' % str(events))
          self.__handle_events(events)
      except IOError, ex:
        if ex.errno != errno.EINTR:
          raise

  def set_halt(self):
    self.__halt = True

  def __handle_events(self, events):
    events = filter(lambda item: item[0] in self.__handlers, events)
    for fd, evt in events:
      handler = self.__handlers[fd]
      try:
        if evt & (EPOLLIN | EPOLLPRI):
          handler.handle_input(fd, self)
        if evt & EPOLLOUT:
          handler.handle_output(fd, self)
        if evt & (EPOLLERR | EPOLLHUP):
          handler.handle_close(fd, self)
      except socket.error, ex:
        pass

    
class Handler:
  def handle_input(self, fd, dispatcher = None):
    pass

  def handle_output(self, fd, dispatcher = None):
    pass

  def handle_close(self, fd, dispatcher = None):
    pass


class RpcListener(Handler):
  def __init__(self, bind_addr, backlog = 10, **kvargs):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.settimeout(2.0)
    sock.bind(bind_addr)
    sock.listen(backlog)
    self.__sock = sock
    self.__bind_addr = bind_addr

  def get_sock(self):
    return self.__sock

  def close(self):
    self.__sock.shutdown(2)
    self.__sock.close()
    self.__sock = None

  def handle_input(self, fd, dispatcher):
    sock, remote_addr = self.__sock.accept()
    logging.info('accept new connection from: %s, fd: %d' %
                 (str(remote_addr), sock.fileno()))
    
    channel = RpcChannel(self, sock, remote_addr)
    channel.set_dispatcher(dispatcher)

  
class RpcChannel(Handler):
  def __init__(self, listener, sock, remote_addr = None, **kvargs):
    sock.setblocking(False)
    self.__sock = sock
    self.__inbuf = InputBuffer()
    self.__outbuf = OutputBuffer()
    self.__dispatcher = None
    self.remote_addr = remote_addr

  def get_sock(self):
    return self.__sock

  def close(self):
    self.__dispatcher.remove_handler(self.__sock.fileno())
    self.__sock.close()
    self.__sock = None
    
  def set_dispatcher(self, dispatcher):
    dispatcher.set_handler(self.__sock.fileno(), self)
    self.__dispatcher = dispatcher
  
  def handle_input(self, fd, dispatcher = None):
    data = self.__sock.recv(1024 * 32)
    logging.debug('recv %d bytes' % len(data))
    if data == '':
      self.handle_close(fd)
    else:
      self.__inbuf.push_data(data)
    packet = self.__inbuf.pop_packet()
    while packet:
      #process packet
      self.__process_packet(packet)
      packet = self.__inbuf.pop_packet()

  def handle_output(self, fd, dispatcher = None):
    data_ptr, data_size = self.__outbuf.get_data_ptr(), \
        self.__outbuf.get_data_size()
    if data_size > 0:
      try:
        sent = self.__sock.send(data_ptr[:data_size])
        self.__outbuf.erase(sent)
      except socket.error, ex:
        if ex.errno != errno.EINTR:
          raise
        else:
          self.handle_output(fd)
    if self.__outbuf.is_empty():
      self.__set_write_notify(False)
      
  def handle_close(self, fd, dispatcher = None):
    if self.__sock:
      self.close()

  def send_response_msg(self, msg, seqno = 0):
    response_data = msg.SerializeToString()
    packet = struct.pack('=IQ%ds' % len(response_data),
                         4 + 8 + len(response_data),
                         seqno,
                         response_data)
    self.__send_packet(packet)
  
  def __send_packet(self, packet):
    if self.__outbuf.is_empty():
      try:
        sent = self.__sock.send(packet)
        logging.debug('send %d bytes' % sent)
        if sent < len(packet):
          self.__outbuf.push_data(packet[sent:])
          self.__set_write_notify(True)
      except socket.error, ex:
        if ex.errno == errno.EINTR:
          self.send_packet(packet)
        else:
          raise
    else:
      self.__outbuf.push_data(packet)

  def __process_packet(self, packet):
    msgsize = len(packet) - 16
    seqno, method_id, request_data = struct.unpack('=QQ%ds' % msgsize, packet)
    obj_manager = self.__dispatcher.get_object_manager()
    response = obj_manager.call_object_method(
      method_id, request_data,
      seqno=seqno, channel=self)
    if response:
      self.send_response_msg(response, seqno)

  def __set_write_notify(self, enable_notify = True):
    mask = NORMAL_POLL_MASK
    if enable_notify:
      mask |= EPOLLOUT
    self.get_dispatcher().set_handler(self.__sock.fileno(),
                                      mask)

    
HEAD_SIZE_PART_LEN = 4
  
class InputBuffer:
  def __init__(self):
    self.__packets = []
    self.__buf = ''

  def push_data(self, data):
    if self.__buf != '':
      data = self.__buf + data
      self.__buf = ''
    
    input_size = len(data)
    if input_size >= HEAD_SIZE_PART_LEN:
      packet_size, = struct.unpack('=I', data[:HEAD_SIZE_PART_LEN])
      logging.debug('packet_size:%d' % packet_size)
      if input_size >= packet_size:
        # we got a packet
        self.__packets.append(data[HEAD_SIZE_PART_LEN:packet_size])
        if input_size > packet_size:
          self.push_data(data[packet_size:])
      else:
        # buffer the data
        self.__buf = data
    else:
      self.__buf = data

  def pop_packet(self):
    if len(self.__packets) > 0:
      return self.__packets.pop(0)
    return None

  def packet_num(self):
    return len(self.__packets)
  

class OutputBuffer:
  min_buf_size = 32 * 1024
  def __init__(self, bufsize = 32 * 1024):
    if bufsize == 0:
      bufsize = min_buf_size
    self.__buf = UserString.MutableString('\0' * bufsize)
    self.__bufsize = bufsize
    self.__datsize = 0

  def push_data(self, data):
    input_size = len(data)
    free_size = self.__bufsize - self.__datsize
    if input_size <= free_size:
      self.__buf[self.__datsize:self.__datsize + input_size] = data
      self.__datsize += input_size
    else:
      self.__buf.extend('\0' * self.__bufsize)
      self.__bufsize *= 2
      self.push_data(data)

  def is_empty(self):
    return (self.__datsize == 0)

  def get_data_ptr(self):
    return self.__buf

  def get_data_size(self):
    return self.__datasize

  def erase(self, size):
    left_size = self.__datsize - size
    if left_size > 0:
      self.__buf[0:left_size] = self.__buf[size:self.__datsize]
    self.__datsize = left_size
    
    if self.__bufsize > min_buf_size and \
          self.__datsize < self.__bufsize / 2:
      new_bufsize = self.__bufsize / 2
      self.__buf[new_bufsize:] = ''
      self.__bufsize = new_bufsize
    
  def clean(self):
    self.__datsize = 0
    

class ObjectManager:
  def __init__(self, svc_list, **kvargs):
    # service table: {service_name:(object,
    #     {method_id:(method_index, method_function, request_class, response_class)}), ...}
    # global method map: {method_id:service_name ...}
    self.__svc_tab = {}
    self.__method_tab = {}
    for svc_full_name in svc_list:
      try:
        svc_obj, methods_map = self.__import_svc(svc_full_name)
        self.__svc_tab[svc_full_name] = (svc_obj, methods_map)
        for method_id in methods_map:
          self.__method_tab[method_id] = svc_full_name
      except Exception, ex:
        logging.error('import %s failed:%s' % (svc_full_name, str(ex)))

  def call_object_method(self, method_id, request_data, **ctx):
    if not self.__method_tab.has_key(method_id):
      raise Exception('invalid method id:%d' % method_id)
    svc_full_name = self.__method_tab[method_id]
    mdata = self.__svc_tab[svc_full_name][1][method_id]
    mfunc, request_class = mdata[1], mdata[2]
    req = request_class()
    req.MergeFromString(request_data)
    return mfunc(req, **ctx)

  def __import_svc(self, svc_full_name):
    logging.info('import service:%s' % svc_full_name)
    i = svc_full_name.rfind('.')
    if i != -1:
      exec 'import %s' % svc_full_name[:i]
    exec 'svc_class = %s' % svc_full_name
    svc_obj = svc_class()
    svc_desc = svc_class.DESCRIPTOR
    index = 0
    methods = {}
    for method_desc in svc_desc.methods:
      method_id = internal.hash_string(method_desc.full_name)
      logging.debug('import method:%d,%s' % (method_id, method_desc.full_name))
      methods[method_id] = (index, getattr(svc_obj, method_desc.name),
                            svc_obj.GetRequestClass(method_desc),
                            svc_obj.GetResponseClass(method_desc))
      index += 1
    return (svc_obj, methods)

    
class Servant:
  def __init__(self, settings, name = None, listener = None,
               kill_notify = None,
               **kvargs):
    self.__killed = False
    self.__kill_notify = kill_notify
    self.__threads = []
    self.name = name or 'No-name-servant'
    self.object_manager = ObjectManager(settings.SERVICE_LIST)
    self.listener = listener or RpcListener((settings.RPC_BIND_ADDR,
                                             settings.RPC_BIND_PORT))
    logging.info('setup servant %s successfully, addr=%s:%d, services=%s' % (
        self.name, settings.RPC_BIND_ADDR, settings.RPC_BIND_PORT,
        str(settings.SERVICE_LIST)))

  def __del__(self):
    try:
      self.cleanup()
    except:
      pass

  def run_server(self, with_handle_sigint = False,
                 with_thread_num = None,                 
                 **kvargs):
    if with_handle_sigint:
      set_signal_handler(self.set_stop)
    if with_thread_num:
      # start thread pool, one pool one dispatcher
      import threading
      for i in range(with_thread_num):
        th = threading.Thread(target = self.__internal_run)
        th.start()
        self.__threads.append(th)
    else:
      self.__internal_run()

  def wait_shutdown(self):
    import time
    while filter(lambda th:th.is_alive(), self.__threads) != []:
      time.sleep(0.5)
  
  def cleanup(self):
    for th in self.__threads:
      th.join()
    self.__threads = []

  def set_stop(self):
    self.__killed = True
    
  def __internal_run(self, *args, **kvargs):    
    dispatcher = Dispatcher(halt_notify = lambda: _check_true(
        self.__killed, self.__kill_notify))
    dispatcher.set_object_manager(self.object_manager)
    dispatcher.set_handler(self.listener.get_sock().fileno(),
                           self.listener)
    logging.info('%s: server running...' % self.name)
    dispatcher.loop(timeout=1.0)
    logging.info('%s: server stopped' % self.name)

    
def set_signal_handler(fun, sigset = 'default-sigset'):
  import signal
  if sigset == 'default-sigset':
    sigset = (signal.SIGQUIT, signal.SIGINT, signal.SIGTERM)
  def handle_signal(sig, frame):
    if sig in sigset:
      fun()
  for sig in sigset:
    signal.signal(sig, handle_signal)

    
def run_default_server():
  import server_setting
  svr = Servant(server_setting)
  svr.run_server(True)
  svr.wait_shutdown()


if __name__ == '__main__':
  import sys
  logging.basicConfig(level=logging.DEBUG, stream=sys.stderr,
                      format='%(asctime)s %(levelname)s %(message)s')
  run_default_server()
