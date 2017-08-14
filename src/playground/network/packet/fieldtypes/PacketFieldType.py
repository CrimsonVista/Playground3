from playground.common import CustomConstant as Constant

class PacketFieldType:
    UNSET = Constant(strValue="Unset Packet Field", boolValue=False)

    def __init__(self, **attributes):
        self._attributes = attributes
        self._data = None
        
    def unsetData(self):
        self._data = self.UNSET
        
    def setData(self, data):
        self._data = data
        
    def data(self):
        return self._data
        
    def createInstance(self):
        cls = self.__class__
        instance = cls(**self._attributes)
        return instance
        
    def getAttribute(self, attr, default=None):
        return self._attributes.get(attr, default)