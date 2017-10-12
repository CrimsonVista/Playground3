'''
Created on Oct 11, 2017

@author: seth_
'''

from io import SEEK_END

class AbstractStreamAdapter(object):
    """
    TODO: Does this class need to exist?
    
    This class represents the necessary functions used for typical encoding.
    Right now, it's only used in PlaygroundStandardPacketEncoder. Does that 
    mean we should make it a module?
    """
    
    @classmethod
    def Adapt(cls, stream):
        if not isinstance(stream, cls):
            return cls(stream)
        return stream
        
    def __init__(self, stream):
        self._stream = stream
        
    def available(self):
        """
        This is duplicate functionality if we have a HighPerformanceStreamIO.
        But we also want to support those that aren't. TODO: Better solution?
        """
        curPos = self._stream.tell()
        self._stream.seek(0, SEEK_END)
        endPos = self._stream.tell()
        self._stream.seek(curPos)
        return endPos-curPos
        
    def seek(self, *args):
        return self._stream.seek(*args)
        
    def tell(self, *args):
        return self._stream.tell(*args)
        
    def read(self, count):
        return self._stream.read(count)
        
    def write(self, data):
        return self._stream.write(data)