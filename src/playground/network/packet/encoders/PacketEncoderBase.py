
from playground.common import CustomConstant

class PacketEncoderBase(object):
    """
    
    """
    DECODE_WAITING_FOR_STREAM = CustomConstant(strValue="Decoding paused; waiting for more data in stream")
    DECODE_COMPLETE           = CustomConstant(strValue="Decoding completed")
    
    class DecodeWaitingForStreamException(Exception):
        pass

    def encode(self, stream, fieldType):
        pass
        # TODO: Error
        
    def decode(self, stream, fieldType):
        pass
        # TODO: Error
        
    def decodeIterator(self, stream, fieldType):
        pass
        # TODO: Error