import asyncio

def policy_synchronized(f):
    """Decorator to ensure that a function is in progress only once. If
    the function is called while another call is waiting async, its
    call will be delayed until the first call is done.

    """
    sem = asyncio.Semaphore(1)
    async def call(*args, **kwargs):
        async with sem:
            return (await f(*args, **kwargs))
    return call

def policy_replace(f):
    """Decorator to ensure that a function is in progress only once. If
    the function is called while another call is waiting async, the
    first call will be canceled.

    """
    task = None
    async def call(*args, **kwargs):
        nonlocal task
        if task:
            task.cancel()
        task = asyncio.Task(f(*args, **kwargs))
        return (await task)
    return call
