#!/usr/bin/env python
#  Author:
#  Muhammad Shahbaz (muhammad.shahbaz@gatech.edu)
#  Rudiger Birkner (Networked Systems Group ETH Zurich)

import json, redis
from multiprocessing.connection import Listener
from threading import Thread

import os, time
import sys
np = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if np not in sys.path:
    sys.path.append(np)
import util.log


''' Server of Reference Monitor to Receive Flow Mods '''
class Server(object):

    def __init__(self, refmon, address, port, key):
        self.logger = util.log.getLogger('RefMon_Server')
        self.logger.info('server: start')

        self.refmon = refmon
        #self.listener = Listener((address, port), authkey=str(key), backlog=100)
        self.listener = Listener((address, port), backlog=128000)
        self.logger.debug('FLANCPORT' + str(port))

    def start(self):
        self.receive = True
        self.receiver = Thread(target=self.receiver)
        self.newReceiver = Thread(target=self.newReceiver)
        self.receiver.start()
        self.newReceiver.start()

    def newReceiver(self):
        r = redis.StrictRedis(host='localhost', port=6379, db=0)
        self.logger.debug('FLANC newReceiver created redis object' + str(r))
        tempIncVar=1
        while self.receive:
            (qname, flow) = r.blpop('flowqueue')
            self.logger.info('REDISSTAT nr of flows in redis: ' + str(r.llen('flowqueue')))
            self.logger.info('REDIS Consuming nr: ' + str(tempIncVar))
            self.refmon.process_flow_mods(json.loads(flow))
            tempIncVar = tempIncVar + 1
        self.logger.debug('RECVSTOP newReceiver is out of receiveloop, thread will end now')

    ''' receiver '''
    def receiver(self):
        while self.receive:
            conn = self.listener.accept()
            self.logger.info('server: accepted connection from ' + str(self.listener.last_accepted))
            msg = None
            while msg is None:
                try:
                    msg = conn.recv()
                    self.logger.info('SUCCESSFUL DEBUGGING: ' + str(msg))
                except Exception as e:
                    self.logger.info('RECEIVING DEBUGGING: ' + str(e.message))
                    self.logger.info('RECEIVING DEBUGGING: ' + str(e.__doc__))
                    pass
            self.logger.info('server: received message')
            self.refmon.process_flow_mods(json.loads(msg))

            conn.close()
            self.logger.info('server: closed connection')
        self.logger.debug('RECVSTOP receiver is out of loop, thread will end now')

    def stop(self):
        self.logger.debug("STOPFLANC setting self.receive to false, stopping listener")
        self.receive = False
        self.receiver.join(1)
