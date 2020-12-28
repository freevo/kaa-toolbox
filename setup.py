# -*- coding: utf-8 -*-
#
# kaa-toolbox - Usefull modules and functions
# Copyright 2020 Dirk Meyer, Jason Tackaberry
#
# Maintainer: Dirk Meyer <https://github.com/Dischi>
#
# Some parts are copied from kaa.base and ported to Python 3
# Copyright 2005-2012 Dirk Meyer, Jason Tackaberry
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

VERSION = '0.1.0'

import os
import setuptools

packages = []
package_dir = {}
for dirpath, dirnames, files in os.walk('src'):
    python_dirpath = 'kaa.toolbox' + dirpath.replace('/', '.')[3:]
    if '__init__.py' in files:
        package_dir[python_dirpath] = dirpath
        packages.append(python_dirpath)

setuptools.setup(
    name = 'kaa-toolbox',
    version = VERSION,
    license = 'LGPL',
    author = 'Dirk Meyer, Jason Tackaberry',
    package_dir = package_dir,
    packages = packages,
    zip_safe=False,
)
