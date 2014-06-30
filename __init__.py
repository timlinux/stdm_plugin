# coding=utf-8
"""
/***************************************************************************
Name                 : Social Tenure Domain Model
Description          : QGIS Entry Point for Social Tenure Domain Model
Date                 : 23/May/13
copyright            : (C) 2013 by John Gitau
email                : gkahiu@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""
# Enable sip2 api before doing any Qt imports
# See http://hub.qgis.org/wiki/quantum-gis/Python_plugin_API_changes_from_18_to_20
import qgis

import os
import sys
sys.path.append(os.path.dirname(__file__))

def classFactory(iface):
    from stdm import stdmqgisloader
    return stdmqgisloader(iface)
