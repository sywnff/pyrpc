# encoding: utf-8

# Copyright 2011 Netease Inc. All Rights Reserved.
# Author: gzsyw@corp.netease.com (Shi Yanwei)

''' common definition for pyprc
'''

class RpcError(Exception):
  def __init__(self, error_code, message = None):
    self.error_code = error_code
    self.message = message
  def __str__(self):
    if self.message:
      return '[%d]%s' % (self.error_code, self.message)
    else:
      return '[%d]' % self.error_code
    

class DomObjectDescriptor:
  def __init__(self, key, handlers, desc = None):
    '''
    handlers: ((handler_function_fullname, input_message_type), ...)
    '''
    self.key = key
    self.handlers = handlers
    self.desc = desc

def defdom(**kvargs):
  return DomObjectDescriptor(**kvargs)
