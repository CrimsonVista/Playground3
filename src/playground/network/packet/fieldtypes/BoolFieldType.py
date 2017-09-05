
from .PacketFieldType import PacketFieldType

class BoolFieldType(PacketFieldType):
    def _setTypedData(self, data):  
        try:
            self._data = bool(data)
        except Exception as e:
            raise ValueError("{} is not a boolean".format(data))