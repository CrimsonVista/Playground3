'''
Created on August 28, 2017
Copied and adapted from Playground 2.0
Original File Created on Aug 20, 2013

@author: sethjn
'''

from playground.network.common import StackingTransport
from .Switch import Switch
import random, asyncio, logging

logger = logging.getLogger(__name__)

class ConstantErrorTransport(StackingTransport):
    """
    This isn't really a stacking transport. 
    However, a basic stacking transport just writes
    everything to the lower layer. And that's mostly 
    what we want.
    
    Why doesn't asyncio have a better basic transport class? 
    
    By default, 1 error every 100k
    """
    
    ErrorHorizon = 100*1024
    ErrorsPerHorizon = 1
    
    def __init__(self, *args, **kargs):
        super().__init__(*args, **kargs)
        self.byteIndex = 0
        
        self.resetBytesToCorrupt()
        
    def resetBytesToCorrupt(self):
        self.bytesToCorrupt = []
        for i in range(self.ErrorsPerHorizon):
            nextBadByte = random.randint(0, self.ErrorHorizon)
            if nextBadByte not in self.bytesToCorrupt:
                self.bytesToCorrupt.append(nextBadByte)
        self.bytesToCorrupt.sort()
        self.curSettings = (self.ErrorsPerHorizon, self.ErrorHorizon)
    
    
    def write(self, data):
        if self.curSettings != (self.ErrorsPerHorizon, self.ErrorHorizon):
            self.resetBytesToCorrupt()
        dataRange = len(data) + self.byteIndex
        while self.bytesToCorrupt and self.bytesToCorrupt[0] < dataRange:
            nextByte = self.bytesToCorrupt.pop(0)
            relativeByte = nextByte - self.byteIndex
            data = data[:relativeByte] + bytes([data[relativeByte] ^ 0xFF]) + data[relativeByte+1:]
        self.byteIndex += len(data)
        if self.byteIndex > self.ErrorHorizon:
            self.byteIndex = 0
            self.resetBytesToCorrupt()
        self.lowerTransport().write(data)
        
class DelayTransport(StackingTransport):
    """
    Will occasionally (about every 100 transmissions), delay
    sending by 1 second.
    """
    Rate = .01
    Delay = 1.0
    
    def write(self, data):
        if random.random() < self.Rate:
            asyncio.get_event_loop().call_later(self.Delay, self.raw_write, data)
        else:
            self.raw_write(data)
            
    def raw_write(self, data):
        try:
            self.lowerTransport().write(data)
        except Exception as e:
            logger.info("Could not write data lower because {}".format(e))
        
class UnreliableSwitch(Switch):      
    def setErrorRate(self, rate, horizon):
        ConstantErrorTransport.ErrorHorizon = horizon
        ConstantErrorTransport.ErrorsPerHorizon = rate
        
    def getDelayRate(self):
        return DelayTransport.Rate, DelayTransport.Delay
    
    def getErrorRate(self):
        return ConstantErrorTransport.ErrorsPerHorizon, ConstantErrorTransport.ErrorHorizon
        
    def setDelayRate(self, rate, delay):
        DelayTransport.Rate = rate
        DelayTransport.Delay = delay
        
    def registerLink(self, address, protocol):
        protocol.transport = DelayTransport(ConstantErrorTransport(protocol.transport))
        super().registerLink(address, protocol)

        
    
