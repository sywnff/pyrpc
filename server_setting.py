# encoding: utf-8

# Copyright 2011 Netease Inc. All Rights Reserved.
# Author: gzsyw@corp.netease.com (Shi Yanwei)

''' default server & dom settings
'''

RPC_BIND_ADDR = '0.0.0.0'
RPC_BIND_PORT = 8008

SERVICE_LIST = (
  # list service implementation here
  'test.echo_service.EchoService',
  )
