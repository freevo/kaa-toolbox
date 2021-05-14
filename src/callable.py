# -*- coding: utf-8 -*-
#
# kaa-toolbox - Usefull modules and functions
# Copyright 2021 Dirk Meyer, Jason Tackaberry
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

__all__ = [ 'Callable', 'DetachedCallable', 'Timer', 'OneShotTimer' ]

import asyncio
import logging

log = logging.getLogger('kaa.toolbox')


class Callable:
    """Wraps an existing callable, binding to it any given args and
    kwargs.

    When the Callable object is invoked, the arguments passed on invocation
    are combined with the arguments specified at construction time and the
    underlying callable is invoked with those arguments.

    """
    def __init__(self, func, *args, **kwargs):
        """
        :param func: callable function or object
        :param args: arguments to be passed to func when invoked
        :param kwargs: keyword arguments to be passed to func when invoked
        """
        self._func = func
        self._args = args
        self._kwargs = kwargs
        self.ignore_caller_args = False
        self.init_args_first = False

    def _merge_args(self, args, kwargs):
        init_args, init_kwargs = self._args, self._kwargs
        if self.ignore_caller_args:
            return init_args, init_kwargs
        if not args and not kwargs:
            return init_args, init_kwargs
        if not init_args and not init_kwargs:
            return args, kwargs
        # Slower paths, where we must copy kwargs in order to merge user
        # kwargs and invocation-time kwargs.
        if self.init_args_first:
            cb_args, cb_kwargs = init_args + args, kwargs.copy()
            cb_kwargs.update(init_kwargs)
        else:
            cb_args, cb_kwargs = args + init_args, init_kwargs.copy()
            cb_kwargs.update(kwargs)
        return cb_args, cb_kwargs

    def __call__(self, *args, **kwargs):
        """Invoke the callable.

        The arguments passed here take precedence over constructor
        arguments if the init_args_first` property is False (default).
        The wrapped callable's return value is returned.

        """
        cb_args, cb_kwargs = self._merge_args(args, kwargs)
        return self._func(*cb_args, **cb_kwargs)


    def __repr__(self):
        """Convert to string for debug.

        """
        return '<%s for %s>' % (self.__class__.__name__, self._func)


    def __eq__(self, func):
        """Compares the given function with the function we're wrapping.

        """
        return id(self) == id(func) or self._func == func


class DetachedCallable(Callable):

    async def __detached_call__(self, obj):
        try:
            if asyncio.iscoroutine(obj):
                obj = await obj
            return obj
        except:
            log.exception('DetachedCallable')
            return None

    def __call__(self, *args, **kwargs):
        try:
            result = super(DetachedCallable, self).__call__(*args, **kwargs)
            asyncio.ensure_future(self.__detached_call__(result))
        except Exception as e:
            log.exception('DetachedCallable')


class Timer(DetachedCallable):

    """Invokes the supplied callback after the supplied interval elapses.
    The Timer is created stopped.

    When the timer interval elapses, we say that the timer is "fired" or
    "triggered," at which time the given callback is invoked.

    If the callback returns True, then the timer will continue to
    fire; otherwise it is automatically stopped.

    """

    restart_when_active = True

    __task = None
    __interval = None

    @property
    def active(self):
        return self.__interval is not None

    async def __detached_call__(self, obj):
        r = await super(Timer, self).__detached_call__(obj)
        if r is True:
            self.__task = asyncio.get_event_loop().call_later(self.__interval, self)
        else:
            self.__task = self.__interval = None

    def start(self, interval, now=False):
        """Start the timer, invoking the callback every *interval* seconds.

        If the timer is already running, it is stopped and restarted
        with the given interval.

        """
        if self.active:
            if not self.restart_when_active:
                return
            self.stop()
        self.__interval = interval
        if now:
            self()
        else:
            self.__task = asyncio.get_event_loop().call_later(self.__interval, self)

    def stop(self):
        if self.__task:
            self.__task.cancel()
        self.__task = self.__interval = None


class OneShotTimer(DetachedCallable):
    """A Timer that gets triggered exactly once when it is started.
    Useful for deferred one-off tasks.

    """

    restart_when_active = True

    __handle = None

    @property
    def active(self):
        return self.__handle is not None

    def __call__(self, *args, **kwargs):
        self.__handle = None
        return super(OneShotTimer, self).__call__(*args, **kwargs)

    def start(self, delay):
        if self.active:
            if not self.restart_when_active:
                return
            self.__handle.cancel()
        self.__handle = asyncio.get_event_loop().call_later(delay, self)

    def stop(self):
        if self.active:
            self.__handle.cancel()
