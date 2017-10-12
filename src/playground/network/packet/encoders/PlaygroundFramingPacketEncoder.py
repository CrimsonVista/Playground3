'''
Created on Oct 11, 2017

@author: seth_
'''
from .PlaygroundStandardPacketEncoder import PlaygroundStandardPacketEncoder, PacketEncoder
from .PacketFramingStream import PacketFramingStreamAdapter

class PlaygroundFramingPacketEncoder(PlaygroundStandardPacketEncoder):
    def encode(self, stream, fieldType):
        typeEncoder = self.GetTypeEncoder(fieldType)
        if typeEncoder == PacketEncoder:
            stream = PacketFramingStreamAdapter.Adapt(stream)
        ret = super().encode(stream, fieldType)
        if typeEncoder == PacketEncoder:
            stream.writeFrame()
        
    def decodeIterator(self, stream, fieldType):
        typeEncoder = self.GetTypeEncoder(fieldType)
        if typeEncoder == PacketEncoder:
            stream = PacketFramingStreamAdapter.Adapt(stream)
        yield from super().decodeIterator(stream, fieldType)
        if typeEncoder == PacketEncoder:
            stream.closeFrame()