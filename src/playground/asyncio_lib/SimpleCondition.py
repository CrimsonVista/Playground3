import asyncio

class SimpleCondition:
    def __init__(self):
        self.rawCondition = asyncio.Condition()

    async def awaitCondition(self, predicate):
        with (await self.rawCondition):
            satisfied = False
            while not satisfied:
                satisfied = await self.rawCondition.wait_for(predicate)
                satisfied = predicate()
            return True

    async def awaitNotify(self):
        with (await self.rawCondition):
            self.rawCondition.notify()
        
    def notify(self):
        asyncio.ensure_future(self.awaitNotify())
        
