'''
Created on Aug 20, 2013

@author: sethjn
'''

import random
from .packets.management import SPMPPacket, PacketType
from playground.asyncio_lib import SimpleCondition

from asyncio import Protocol
import io


class SPMPClientProtocol(Protocol):
    def __init__(self, security=None):
        self._security = security
        self._responses = {}
        self._responseCondition = SimpleCondition()
        self._deserializer = SPMPPacket.Deserializer()
        
    def connection_made(self, transport):
        self.transport = transport
        
    def connection_lost(self, reason=None):
        self.transport = None
        
    def data_received(self, data):
        self._deserializer.update(data)
        for packet in self._deserializer.nextPackets():
            result, error = packet.result, packet.error
            if error == packet.UNSET:
                error = None
            self._responses[packet.requestId] = (result, error)
            self._responseCondition.notify()
        
    async def query(self, cmd, *args):
        request = SPMPPacket()
        request.generateRequestId()
        request.request = cmd
        request.args = list(args)
        request.result = ""
        self._security and self._security.addSecurityParameters(self, request)
        
        self.transport.write(request.__serialize__())
        
        cond = await self._responseCondition.awaitCondition(lambda: request.requestId in self._responses)
        return self._responses[request.requestId]

class SPMPServerProtocol(Protocol):
    def __init__(self, device, apiMap, security=None):
        '''
        Creates an instance of the ChaerponeProtocol class with the
        server as the argument.
        '''
        self._device = device
        self._apiMap = apiMap
        self._deserializer = SPMPPacket.Deserializer()
        self._security=security
        self.transport = None
        
    def connection_lost(self, reason=None):
        self.transport = None
        
    def connection_made(self, transport):
        self.transport = transport
            
    def data_received(self, buf):
        self._deserializer.update(buf)
        for packet in self._deserializer.nextPackets():
            self._processSpmpRequest(packet)
        
    def _processSpmpRequest(self, request):
        if self._security and not self._security.authorized(self.transport, packet):
            return
        
        # get the command and its args
        cmd = request.request
        args = list(request.args)
        
        # generate a response (potentially with an error)
        response = request
        response.result = ""
        error = None
        if cmd not in self._apiMap:
            error = "Unknown request '{}' to device [{}]".format(cmd, self._device)
        else:
            try:
                response.result = self._apiMap[cmd](*args)
            except Exception as error:
                error = str(error)
        if error:
            response.error = error
        self.transport.write(response.__serialize__())
            
class HiddenSPMPServerProtocol(SPMPServerProtocol):
    def __init__(self, mainProtocol, device, apiMap, security=None):
        super().__init__(device, apiMap, security)
        self._mainProtocol = mainProtocol
        self._deserializer = PacketType.Deserializer()
    
    def data_received(self, data):
        self._deserializer.update(data)
        for packet in self._deserializer.nextPackets():
            if isinstance(packet, SPMPPacket):
                #self.transport.write(packet.__serialize__())
                self._processSpmpRequest(packet)
            else:
                self._mainProtocol.data_received(packet.__serialize__())
                
    def connection_made(self, transport):
        super().connection_made(transport)
        self._mainProtocol.connection_made(transport)
        
    def connection_lost(self, reason=None):
        super().connection_lost(reason)
        self._mainProtocol.connection_lost(reason)
    
#if __name__=="__main__":
#    basicUnitTest()
#    print("Basic Unit Test completed successfully")
    
    