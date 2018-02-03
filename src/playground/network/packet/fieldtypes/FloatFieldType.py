'''
Created on Jan 29, 2018

@author: seth_
'''

from .PacketFieldType import PacketFieldType

class FloatFieldType(PacketFieldType):
    def _setTypedData(self, data):  
        try:
            self._data = float(data)
        except Exception as e:
            raise ValueError("{} is not a float".format(data))