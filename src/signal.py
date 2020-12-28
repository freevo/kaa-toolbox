# -*- coding: utf-8 -*-
#
# kaa-toolbox - Usefull modules and functions
# Copyright 2020 Dirk Meyer, Jason Tackaberry
#
# Maintainer: Dirk Meyer <https://github.com/Dischi>
#
# Originally from kaa.base for Python 2.x
# Copyright 2010-2014 Dirk Meyer, Jason Tackaberry
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

__all__ = [ 'Signal', 'Signals' ]

import logging
import functools
import asyncio

from .asyncio import detach

log = logging.getLogger('kaa.toolbox')


class Signal:
    __slots__ = '_callbacks', '_deferred_args', '_changed_cb', '_future'

    """
    Create a Signal object to which callbacks can be connected and later
    invoked in sequence when the Signal is emitted.
    """
    # Defines the maximum number of connections to a signal.  Attempting to
    # connect more than this many callbacks will trigger an exception.
    MAX_CONNECTIONS = 1000

    # Constants used for the action parameter for changed_cb.
    CONNECTED = 1
    DISCONNECTED = 2

    def __init__(self, changed_cb=None):
        """
        :param changed_cb: corresponds to the :attr:`~Signal.changed_cb` property.
        :type changed_cb: callable
        """
        super().__init__()
        if changed_cb and not callable(changed_cb):
            raise TypeError('changed_cb must be callable')
        self._changed_cb = changed_cb
        self._callbacks = []
        self._deferred_args = None
        self._future = None


    @property
    def changed_cb(self):
        """
        Callable to be invoked whenever a callback is connected to or
        disconnected from the Signal.

        .. describe:: def callback(signal, action)

           :param signal: the :class:`~Signal` object acted upon
           :param action: either ``Signal.CONNECTED`` or ``Signal.DISCONNECTED``
        """
        return self._changed_cb


    @changed_cb.setter
    def changed_cb(self, callback):
        if callback and not callable(callback):
            raise TypeError('value must be callable')
        self._changed_cb = callback


    @property
    def callbacks(self):
        """
        Tuple containing the callbacks connected to this signal.

        Because this value is a tuple, it cannot be manipulated directly.  Use
        :meth:`~Signal.connect` and :meth:`~Signal.disconnect` instead.
        """
        return tuple(self._callbacks)


    def __iter__(self):
        for cb in self._callbacks:
            yield cb


    def __len__(self):
        return len(self._callbacks)


    def __bool__(self):
        return True


    def __contains__(self, func):
        for cb in self._callbacks:
            if cb.func == func:
                return True
        return False


    def _connect(self, callback, args=(), kwargs={}, once=False, pos=-1):
        """
        Connects a new callback to the signal.  args and kwargs will be bound
        to the callback and merged with the args and kwargs passed during
        emit().
        """
        if not callable(callback):
            raise TypeError('callback must be callable, got %s instead.' % callback)

        if len(self._callbacks) >= Signal.MAX_CONNECTIONS:
            raise ValueError('Number of callbacks exceeds Signal.MAX_CONNECTIONS limit (%d)' % Signal.MAX_CONNECTIONS)

        callback = functools.partial(callback, *args, **kwargs)
        callback._signal_once = once

        if pos == -1:
            pos = len(self._callbacks)

        self._callbacks.insert(pos, callback)
        self._changed(Signal.CONNECTED)

        if self._deferred_args:
            # Clear deferred args before emitting, in case callbacks do emit_deferred().
            deferred_args, self._deferred_args = self._deferred_args, None
            for args, kwargs in deferred_args:
                self.emit(*args, **kwargs)

        return callback


    def connect(self, callback, *args, **kwargs):
        """
        Connects the callback with the (optional) given arguments to be invoked
        when the signal is emitted.

        :param callback: callable invoked when signal emits
        :param args: optional non-keyword arguments passed to the callback
        :param kwargs: optional keyword arguments passed to the callback.
        :return: a new :class:`functools.partial` object encapsulating the supplied
                 callable and arguments.
        """
        return self._connect(callback, args, kwargs)


    def connect_once(self, callback, *args, **kwargs):
        """
        Variant of :meth:`~Signal.connect` where the callback is automatically
        disconnected after one signal emission.
        """
        return self._connect(callback, args, kwargs, once=True)


    def connect_first(self, callback, *args, **kwargs):
        """
        Variant of :meth:`~Signal.connect` in which the given callback is
        inserted to the front of the callback list.
        """
        return self._connect(callback, args, kwargs, pos=0)


    def connect_first_once(self, callback, *args, **kwargs):
        """
        Variant of :meth:`~Signal.connect_once` in which the given callback is
        inserted to the front of the callback list.
        """
        return self._connect(callback, args, kwargs, once=True, pos=0)


    def _disconnect(self, callback, args, kwargs):
        assert(callable(callback))
        noargs = len(args) == len(kwargs) == 0
        new_callbacks = []
        for cb in self._callbacks[:]:
            cbargs, cbkwargs = cb.args, cb.keywords or {}
            if (cb.func == callback and (noargs or (args, kwargs) == (cbargs, cbkwargs))) or cb == callback:
                # This matches what we want to disconnect.
                continue
            new_callbacks.append(cb)

        num_removed = len(new_callbacks) - len(self._callbacks)
        if num_removed:
            self._callbacks = new_callbacks
            self._changed(Signal.DISCONNECTED)
        return num_removed


    def _changed(self, action):
        """
        Called when a callback was connected or disconnected.

        :param action: Signal.CONNECTED or Signal.DISCONNECTED
        """
        if self._changed_cb:
            try:
                self._changed_cb(self, action)
            except CallableError:
                self._changed_cb = None


    def disconnect(self, callback, *args, **kwargs):
        """
        Disconnects the given callback from the signal so that future emissions
        will not invoke that callback any longer.

        If neither args nor kwargs are specified, all instances of the given
        callback (regardless of what arguments they were originally connected with)
        will be disconnected.

        :param callback: either the callback originally connected, or the
                         :class:`functools.partial` object returned by
                         :meth:`~Signal.connect`.
        :return: the number of callbacks removed from the signal
        """
        return self._disconnect(callback, args, kwargs)


    def disconnect_all(self):
        """
        Disconnects all callbacks from the signal.
        """
        count = self.count()
        self._callbacks = []
        if count > 0:
            self._changed(Signal.DISCONNECTED)


    def emit(self, *args, **kwargs):
        """
        Emits the signal, passing the given arguments callback connected to the signal.

        :return: False if any of the callbacks returned False, and True otherwise.
        """
        retval = True
        if self._callbacks:
            for cb in self._callbacks[:]:
                if cb._signal_once:
                    self.disconnect(cb)

                try:
                    result = cb(*args, **kwargs)
                    if asyncio.iscoroutine(result):
                        detach(result)
                    if result == False:
                        retval = False
                except Exception as e:
                    log.exception('Exception while emitting signal')

        if self._future:
            if len(args) == 1:
                if isinstance(args[0], Exception):
                    self._future.set_exception(args[0])
                else:
                    self._future.set_result(args[0])
            else:
                self._future.set_result(args)
            self._future = None

        return retval


    def emit_deferred(self, *args, **kwargs):
        """
        Queues the emission until after the next callback is connected.

        This allows a signal to be 'primed' by its creator, and the handler
        that subsequently connects to it will be called with the given
        arguments.
        """
        if self._deferred_args is None:
            self._deferred_args = [(args, kwargs)]
        else:
            self._deferred_args.append((args, kwargs))


    def emit_when_handled(self, *args, **kwargs):
        """
        Emits the signal if there are callbacks connected, or defers it until
        the first callback is connected.
        """
        if self.count():
            return self.emit(*args, **kwargs)
        else:
            self.emit_deferred(*args, **kwargs)


    def count(self):
        """
        Returns the number of callbacks connected to the signal.

        Equivalent to ``len(signal)``.
        """
        return len(self._callbacks)


    def future(self):
        """
        Returns a Future object that is done when the signal next emits.

        :return: a new :class:`~asyncio.Future' object
        """
        if not self._future:
            self._future = asyncio.Future()
        return self._future



class Signals(dict):
    """
    A collection of one or more Signal objects, which behaves like a dictionary
    (with key order preserved).

    The initializer takes zero or more arguments, where each argument can be a:
        * dict (of name=Signal() pairs) or other Signals object
        * tuple/list of (name, Signal) tuples
        * str representing the name of the signal
    """
    def __init__(self, *signals):
        super().__init__()
        # Preserve order of keys.
        self._keys = []
        for s in signals:
            if isinstance(s, dict):
                # parameter is a dict/Signals object
                self.update(s)
                self._keys.extend(s.keys())
            elif isinstance(s, str):
                # parameter is a string
                self[s] = Signal()
                self._keys.append(s)
            elif isinstance(s, (tuple, list)) and len(s) == 2:
                # In form (key, value)
                if isinstance(s[0], basestring) and isinstance(s[1], Signal):
                    self[s[0]] = s[1]
                    self._keys.append(s[0])
                else:
                    raise TypeError('With form (k, v), key must be string and v must be Signal')

            else:
                # parameter is something else, bad
                raise TypeError('signal key must be string')


    def __delitem__(self, key):
        super().__delitem__(key)
        self._keys.remove(key)


    def keys(self):
        """
        List of signal names (strings).
        """
        return self._keys


    def values(self):
        """
        List of Signal objects.
        """
        return [self[k] for k in self._keys]


    def __add__(self, signals):
        return Signals(self, *signals)


    def add(self, *signals):
        """
        Creates a new Signals object by merging all signals defined in
        self and the signals specified in the arguments.

        The same types of arguments accepted by the initializer are allowed
        here.
        """
        return Signals(self, *signals)


    def subset(self, *names):
        """
        Returns a new Signals object by taking a subset of the supplied
        signal names.

        The keys of the new Signals object are ordered as specified in the
        names parameter.

            >>> yield signals.subset('pass', 'fail').any()
        """
        return Signals(*[(k, self[k]) for k in names])


    def futures(self):
        return [self[k].future() for k in self._keys]


    def any(self):
        return asyncio.wait(self.futures(), return_when=asyncio.FIRST_COMPLETED)


    def all(self, return_exceptions=True):
        return asyncio.gather(*self.futures(), return_exceptions=return_exceptions)
