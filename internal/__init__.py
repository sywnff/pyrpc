# encoding: utf-8

# Copyright 2011 Netease Inc. All Rights Reserved.
# Author: gzsyw@corp.netease.com (Shi Yanwei)

''' module py-rpc.internal
'''

import _internal

hash_string = lambda x: int(_internal.hash_string(x))
