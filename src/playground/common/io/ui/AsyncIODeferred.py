import asyncio

# A wrapper class for asyncio.Future so we can use errorBacks
# (also so I don't have to change a hundred lines of code...)
class Deferred:
    def __init__(self):
        self.f = asyncio.Future()

    def __cb(self, fut, func):
        # might want to remove .done() check to better catch errors
        # (.result() throws an error if not done)
        if fut.done() and fut.result():
            return func(fut.result())
        return None # should I return an exception instead?

    def addCallback(self, func):
        self.f.add_done_callback(lambda fut: self.__cb(fut,func))

    def callback(self, res):
        self.f.set_result(res)
        return self.f # is this necessary?

    def __eb(self, fut, func):
        # might want to remove .done() check to better catch errors
        # (.exception() throws an error if not done)
        if fut.done() and fut.exception():
            return func(fut.exception())
        return None # should I return an exception instead?

    def addErrback(self, func):
        self.f.add_done_callback(lambda fut: self.__eb(fut,func))

    def errback(self, exc):
        self.f.set_exception(exc)
        return self.f # is this necessary?
