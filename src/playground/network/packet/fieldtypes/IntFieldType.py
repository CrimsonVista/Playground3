
from .PacketFieldType import PacketFieldType

class IntFieldType(PacketFieldType):
    def _setTypedData(self, data):  
        try:
            self._data = int(data)
        except Exception as e:
            raise ValueError("{} is not a int".format(data))