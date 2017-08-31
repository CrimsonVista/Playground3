"""
NOTE: We're currently tying this class to asyncio. 
Consider making an asyncio  implementation that 
can be swapped out
"""
import asyncio

class TimePeriod:
    def __init__(self, seconds):
        self._seconds = seconds
        
    def seconds(self):
        return self._seconds

class Seconds(TimePeriod):
    pass
    
class Minutes(TimePeriod):
    def __init__(self, minutes):
        super().__init__(minutes*60)

class Timer:
    def __init__(self, timePeriod, callback, *args):
        self._delay = timePeriod.seconds()
        self._callback = callback
        self._callbackArgs = args
        self._task = None
        self._loop = asyncio.get_event_loop()
        
    def _fireCallback(self):
        if self._delay:
            """
            The delay has been increased while we waited.
            Just call "start" again.
            """
            self.start()
        else:
            self._callback(*self._callbackArgs)
        
    def extend(self, timePeriod):
        self._delay = timePeriod.seconds()
        
    def cancel(self):
        self._task.cancel()
        
    def start(self):
        origDelay = self._delay
        self._delay = 0
        self._task = self._loop.call_later(origDelay, self._fireCallback)
    
    def expire(self):
        self._task.cancel()
        self._callback(*self._callbackArgs)
        
def basicUnitTest():
    from playground.asyncio_lib.testing import TestLoopEx
            
    testLoop = TestLoopEx()
    asyncio.set_event_loop(testLoop)
    
    results = []
    def callback(results, index):
        results.append("Callback{}".format(index))
        
    t1 = Timer(Seconds(10), callback, results, 0)
    t2 = Timer(Seconds(20), callback, results, 1)
    t3 = Timer(Seconds(20), callback, results, 2)
    
    t1.start()    
    t2.start()
    t3.start()
    assert len(results) == 0

    testLoop.advanceClock(5) # 5
    assert len(results) == 0
    
    testLoop.advanceClock(10) # 15
    assert len(results) == 1
    assert results.pop() == "Callback0"
    
    t2.extend(Seconds(10))    # should now fire at 30
    t3.extend(Seconds(10))    # should now fire at 30
    testLoop.advanceClock(10) # 25
    assert len(results) == 0
    
    t3.cancel()
    testLoop.advanceClock(10) # 35
    assert len(results) == 1
    assert results.pop() == "Callback1"
    
    testLoop.close()
    
if __name__=="__main__":
    basicUnitTest()
    print("Basic Unit Test completed successfully")