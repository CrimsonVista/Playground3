
from .PacketFieldType import PacketFieldType

class StringFieldType(PacketFieldType):
    
    def _setTypedData(self, data):  
        try:
            self._data = str(data)
        except Exception as e:
            raise ValueError("{} is not a string".format(data))