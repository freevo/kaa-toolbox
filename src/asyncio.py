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

import os
import time
import asyncio
import logging

log = logging.getLogger('kaa.toolbox')

def detach(obj, log=log):
    """Detach a task from the mainloop

    Similar to ensure_future the task will run in the background. The
    main difference is, that exceptions will be catched and logged
    with the given logging instance. If the obj is no coroutine, this
    functions does nothing.

    """
    async def handler():
        try:
            await obj
        except asyncio.CancelledError:
            pass
        except:
            log.exception('detach')
    if asyncio.iscoroutine(obj):
        asyncio.ensure_future(handler())


def call_later(timer, callback, *args, log=log, **kwargs):
    """call_later version with coroutine, *args and **kwargs support

    Call the given function with its *args and **kwargs in timer
    seconds. Unlike the original, callback may also be a
    coroutine. This helper ensures catching exceptions. If log is
    given this logger will be used to log exceptions.

    """
    def _callback():
        try:
            detach(callback(*args, **kwargs), log=log)
        except:
            log.exception('call_later')
    return asyncio.get_event_loop().call_later(timer, _callback)

_is_clock_synchronized_t = 0

if not os.path.exists('/dev/rtc'):
    # We do not have a real time clock (e.g. raspberry). Asume a bad
    # clock state for three minutes after boot
    uptime = float(open('/proc/uptime', 'r').read().split(' ')[0])
    _is_clock_synchronized_t = time.time() - uptime + 180
    _clock_difference = int(time.time() - time.monotonic())

def is_clock_synchronized():
    # This function should return true if the time is synchronized and
    # therefore, we can be sure our timers are working correctly.
    global _is_clock_synchronized_t
    if not _is_clock_synchronized_t:
        return True
    if abs(int(time.time() - time.monotonic() - _clock_difference)) > 10:
        log.debug('system clock jumped more than 10 seconds; clocks are in sync now')
        _is_clock_synchronized_t = 0
        return True
    if _is_clock_synchronized_t > time.time():
        return False
    log.debug('system clock synced after three minutes')
    _is_clock_synchronized_t = 0
    return True


async def _call_at(timestamp, callback, *args, log=log, **kwargs):
    while True:
        secs = max(timestamp - time.time(), 0.1)
        if not is_clock_synchronized() and secs > 90:
            # The clock is not synchronized. Do not trust it and
            # check again in one minute
            await asyncio.sleep(60)
            continue
        if secs > 3 * 3600:
            # More than three hours in the future. To be safe with
            # time jumps between time.time() and loop.time(), check
            # again one hour before start.
            await asyncio.sleep(min(secs - 3600, 23 * 60 * 60))
            continue
        await asyncio.sleep(secs)
        break
    try:
        detach(callback(*args, **kwargs), log=log)
    except:
        log.exception('call_at')


def call_at(timestamp, callback, *args, log=log, **kwargs):
    """call_at version with coroutine, argument and system time support

    Call the given function with its *args and **kwargs in timer
    seconds. Unlike the original, callback may also be a
    coroutine. This helper ensures catching exceptions. If log is
    given this logger will be used to log exceptions.

    Unlike th original, this function uses the system time and not the
    loop time (time.monotonic).
    """
    return asyncio.Task(_call_at(timestamp, callback, *args, log=log, **kwargs))
