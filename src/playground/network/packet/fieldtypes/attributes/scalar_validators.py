from .Validator import Validator

# These classes could be Validator instances, but provides less error reporting in exceptions.

class MaxValueValidator(Validator):
    def __init__(self, baseAttributes=None):
        super().__init__(lambda data, maxValue: data <= maxValue, baseAttributes)
MaxValue = MaxValueValidator()        

class MinValueValidator(Validator):        
    def __init__(self, baseAttributes=None):
        super().__init__(lambda data, minValue: data >= minValue, baseAttributes)
MinValue = MinValueValidator()

class BitsValidator(MaxValueValidator):
    def __init__(self, baseAttributes=None):
        newBaseAttributes = [MaxValue]
        if baseAttributes != None: newBaseAttributes += baseAttributes
        super().__init__(newBaseAttributes)
        
    def validate(self, data, attrValue):
        return super().validate(data, 2**attrValue)
        
    def translateAttributeValue(self, base, attrValue):
        if base == MaxValue:
            return (2**attrValue)-1
        else:
            return super().translateAttributeValue(base, attrValue)
Bits = BitsValidator()