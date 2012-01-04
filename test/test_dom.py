# encoding: utf-8

# Copyright 2011 Netease Inc. All Rights Reserved.
# Author: gzsyw@corp.netease.com (Shi Yanwei)

''' dom test
'''

import sys
sys.path.append('../')

import dom
import dom_test_pb2
import time

def DOM1_Handler(msg, **kvargs):
  print 'DOM1_Handler:a=%d' % msg.a
  for lab in msg.label:
    print 'label: %s' % lab
  for t in msg.time:
    print 'time: %f' % t
  respond = dom_test_pb2.DOMTest1()
  respond.CopyFrom(msg)
  respond.label.append('server')
  respond.time.append(time.time())
  dom.SendMessageToKey('dom_test_client_key', respond)

def DOM2_Handler(msg, **kvargs):
  print 'DOM1_Handler:a=%d' % msg.a
  for lab in msg.label:
    print 'label: %s' % lab
  for t in msg.time:
    print 'time: %f' % t

