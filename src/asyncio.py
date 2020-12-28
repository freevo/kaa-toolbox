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
