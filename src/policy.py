import time
import logging
import asyncio
import functools

from .asyncio import call_later

log = logging.getLogger('kaa.toolbox')

class policy:
    def __get__(self, instance, owner):
        # Make the decorator a descriptor and return a new object for
        # the instance. We need to cache the new policy interact with
        # it later.
        name = '_kaa_%s_%s' % (self.__class__.__name__, self.func.__name__)
        if getattr(instance, name, None) == None:
            func = functools.wraps(self.func)(functools.partial(self.func, instance))
            setattr(instance, name, self.__class__(func))
        return getattr(instance, name)


class policy_replace(policy):
    """Decorator to ensure that a function is in progress only once.

    If the function is called while another call is waiting async, the
    first call will be canceled.
    """
    def __init__(self, func):
        self.func = func
        self.task = None

    async def __call__(self, *args, **kwargs):
        if self.task:
            self.task.cancel()
        self.task = asyncio.Task(self.func(*args, **kwargs))
        return (await self.task)


class policy_synchronized(policy):
    """Decorator to ensure that a function is in progress only once.

    If the function is called while another call is waiting async, its
    call will be delayed until the first call is done.
    """
    def __init__(self, func):
        self.func = func
        self.sem = asyncio.Semaphore(1)

    async def __call__(self, *args, **kwargs):
        async with self.sem:
            return (await self.func(*args, **kwargs))


class policy_task(policy):
    """Decorator to mark a function as Task

    Only one instance of the function can run at any given time. For
    class methods, each class instance can have its own Task. A
    function decorated as policy_task has a start and a stop method.

    @policy_task
    async def monitor():
        ...

    monitor.start()
    monitor.cancel()
    """
    def __init__(self, func):
        self.func = func
        self.task = None
        self.__name__ = func.__name__
        self.__doc__ = func.__doc__

    def start(self, *args, **kwargs):
        """Start the function as asyncio.Task
        """
        if self.task:
            self.task.cancel()
        self.task = asyncio.Task(self.func(*args, **kwargs))

    def cancel(self):
        """Cancel the running Task object
        """
        if self.task:
            self.task.cancel()
        self.task = None

    def done(self):
        """Return True if the Task is done.

        A Task is done when the wrapped coroutine either returned a
        value, raised an exception, or the Task was cancelled.
        """
        if self.task:
            if not self.task.done():
                return False
            self.task = None
        return True


class policy_clock(policy):
    """Run the decorated function at a specific time

    Only one instance of the function can be scheduled at any given
    time. For class methods, each class instance can have its own
    timer. A function decorated as policy_timer is started with the
    time to be executed. Starting the function with zero as time will
    terminate a current timer.
    """
    def __init__(self, func):
        self.timer = None
        self.value = 0
        self.func = func
        self.__name__ = func.__name__
        self.__doc__ = func.__doc__

    def __call__(self, t, log=log):
        self.log = log
        self.name = '%s.%s' % (getattr(self.func, '__module__', None), self.func.__name__)
        if t < time.time() - 60*60*24:
            # More than one day ago? Ignore this timer
            t = 0
        if self.value == t:
            return
        self.value = t
        if self.timer:
            self.timer.cancel()
        if not t:
            self.timer = None
            log.info('no timer for %s scheduled' % self.name)
            return
        log.info('timer %s at %s' % (self.name, time.ctime(t)))
        if t-time.time() > 60*60*23.5:
            # Set timer. Due to a Python bug not more than one day in the
            # future. Let emit do a reschedule.
            self.timer = call_later(60*60*23, self.emit, t, log, log=log)
        else:
            # Set timer. Make sure the timer is always positive
            self.timer = call_later(max(t-time.time(), 0.1), self.emit, t, log, log=log)

    def stop(self):
        self.value = 0
        if self.timer:
            self.timer.cancel()
            self.timer = None

    async def emit(self, t, log):
        self.timer = None
        self.value = 0
        if t - time.time() > 10:
            # We should not wakeup yet; restart timer
            log.info('restart for %s' % self.name)
            return self(t, log=log, name=self.name)
        try:
            log.info('emit for %s' % self.name)
            obj = self.func()
            if asyncio.iscoroutine(obj):
                await obj
        except:
            log.exception('emit')
