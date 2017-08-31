
from .PacketFieldType import PacketFieldType

class BufferFieldType(PacketFieldType):
    
    def _setTypedData(self, data):  
        if not isinstance(data, bytes):
            raise ValueError("{} is not bytes".format(data))
        self._data = data