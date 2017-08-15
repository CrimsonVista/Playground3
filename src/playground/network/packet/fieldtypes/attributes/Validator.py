from .FieldTypeAttribute import FieldTypeAttribute

class Validator(FieldTypeAttribute):
    def __init__(self, predicate, baseAttributes=None):
        super().__init__(baseAttributes)
        self._predicate = predicate
        
    def validate(self, data, attrValue):
        return self._predicate(data, attrValue)
        
