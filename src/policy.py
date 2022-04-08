# -*- coding: utf-8 -*-
#
# kaa-toolbox - Usefull modules and functions
# Copyright 2020 Dirk Meyer, Jason Tackaberry
#
# Maintainer: Dirk Meyer <https://github.com/Dischi>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MER-
# CHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA
#

__all__ = [ 'policy_replace', 'policy_synchronized', 'policy_task', 'policy_clock', 'policy_cron' ]

import time
import logging
import asyncio
import functools

from .asyncio import call_later

log = logging.getLogger('kaa.toolbox')

class _policy:
    def __get__(self, instance, owner):
        # Make the decorator a descriptor and return a new object for
        # the instance. We need to cache the new policy interact with
        # it later.
        name = '_kaa_%s_%s' % (self.__class__.__name__, self.func.__name__)
        if getattr(instance, name, None) == None:
            func = functools.wraps(self.func)(functools.partial(self.func, instance))
            setattr(instance, name, self.__class__(func))
        return getattr(instance, name)


class policy_replace(_policy):
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


class policy_synchronized(_policy):
    """Decorator to ensure that a function is in progress only once.

    If the function is called while another call is waiting async, its
    call will be delayed until the first call is done.
    """
    def __init__(self, func):
        self.func = func
        self.lock = asyncio.Lock()

    async def __call__(self, *args, **kwargs):
        async with self.lock:
            return (await self.func(*args, **kwargs))


class policy_task(_policy):
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


class policy_clock(_policy):
    """Run the decorated function at a specific time

    Only one instance of the function can be scheduled at any given
    time. For class methods, each class instance can have its own
    timer. A function decorated as policy_clock is started with the
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
        # Set timer. Make sure the timer is always positive
        self.timer = call_later(max(t-time.time(), 0.1), self.emit, t, log, log=log)

    def stop(self):
        self.value = 0
        if self.timer:
            self.timer.cancel()
            self.timer = None

    async def emit(self, t, log):
        log.info('emit for %s' % self.name)
        self.timer = None
        self.value = 0
        try:
            obj = self.func()
            if asyncio.iscoroutine(obj):
                await obj
        except:
            log.exception('policy_clock')


class policy_cron:
    """Call the function repeatedly at the given time

    A function decorated with policy_cron will be called repeatedly
    based on the given hours and minutes. The scheduler takes care of
    day changes. The cron will be started just be decorating a
    function is stopped by returning False (or raising an exception).

    """
    def __init__(self, hours=range(24), minutes=0):
        if isinstance(minutes, int):
            minutes = [ minutes ]
        if isinstance(hours, int):
            hours = [ hours ]
        self.minutes = sorted(list(minutes))
        self.hours = sorted(list(hours))

    def start_next(self):
        now = time.localtime()
        secs = - now.tm_sec
        hour = now.tm_hour
        for m in self.minutes:
            if m > now.tm_min:
                secs += (m-now.tm_min) * 60
                break
        else:
            secs += (self.minutes[0]-now.tm_min) * 60
            hour += 1
        for h in self.hours:
            if h >= hour:
                secs += (h-now.tm_hour)*3600
                break
        else:
            secs += (24+self.hours[0]-now.tm_hour)*3600
        call_later(secs, self.execute)

    async def execute(self):
        try:
            obj = self.func()
            if asyncio.iscoroutine(obj):
                obj = await obj
        except:
            log.exception('policy_cron')
        if obj is not False:
            self.start_next()

    def __call__(self,f):
        self.func = f
        self.start_next()
        return f
