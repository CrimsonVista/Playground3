import asyncio

class SimpleCondition:
    def __init__(self):
        self.rawCondition = asyncio.Condition()

    async def awaitCondition(self, predicate):
        with (await self.rawCondition):
            return await self.rawCondition.wait_for(predicate)

    async def awaitNotify(self):
        with (await self.rawCondition):
            self.rawCondition.notify()
        
    def notify(self):
        asyncio.ensure_future(self.awaitNotify())
        