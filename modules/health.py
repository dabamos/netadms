#!/usr/bin/env python3
"""
Copyright (c) 2016 Hochschule Neubrandenburg.

Licensed under the EUPL, Version 1.1 or - as soon they will be approved
by the European Commission - subsequent versions of the EUPL (the
"Licence");

You may not use this work except in compliance with the Licence.

You may obtain a copy of the Licence at:

    http://ec.europa.eu/idabc/eupl

Unless required by applicable law or agreed to in writing, software
distributed under the Licence is distributed on an "AS IS" basis,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the Licence for the specific language governing permissions and
limitations under the Licence.
"""

import logging
import threading
import time

from modules.prototype import Prototype

"""Module for health services."""

logger = logging.getLogger('openadms')


class DeathExaminer(Prototype):

    def __init__(self, name, config_manager, sensor_manager):
        Prototype.__init__(self, name, config_manager, sensor_manager)
        config = self._config_manager.config.get(self._name)

        self._enabled = config.get('Enabled')
        self._max_age = config.get('MaxAge')
        self._ports = {}

        self._thread = threading.Thread(target=self._check)
        self._thread.daemon = True
        self._thread.start()

    def action(self, obs):
        port_name = obs.get('PortName')
        self._ports[port_name] = time.time()

        return obs

    def _check(self):
        if not self._enabled:
            return

        zombies = []

        while True:
            now = time.time()

            for port_name, last_update in self._ports.items():
                if now - last_update > self._max_age:
                    m = round(self._max_age / 60)

                    if m == 0:
                        t = '{} seconds'.format(self._max_age)
                    else:
                        t = '{} minutes'.format(m)

                    # Fire error message.
                    logger.error('Sensor on port "{}" seems to be dead (no '
                                 'response since {})'.format(port_name, t))
                    # Mark port as zombie.
                    zombies.append(port_name)

            # Delete the zombies from the ports dictionary.
            for zombie in zombies:
                del(self._ports[zombie])

            # Clear the zombies list.
            del(zombies[:])

            time.sleep(1)
