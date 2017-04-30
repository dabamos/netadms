#!/usr/bin/env python3
"""
Copyright (c) 2017 Hochschule Neubrandenburg.

Licenced under the EUPL, Version 1.1 or - as soon they will be approved
by the European Commission - subsequent versions of the EUPL (the
"Licence");

You may not use this work except in compliance with the Licence.

You may obtain a copy of the Licence at:

    https://joinup.ec.europa.eu/community/eupl/og_page/eupl

Unless required by applicable law or agreed to in writing, software
distributed under the Licence is distributed on an "AS IS" basis,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the Licence for the specific language governing permissions and
limitations under the Licence.
"""

"""Prototype class which can be used as a blueprint for other OpenADMS
modules."""

__author__ = 'Philipp Engel'
__copyright__ = 'Copyright (c) 2017 Hochschule Neubrandenburg'
__license__ = 'EUPL'

from core.manager import *
from core.observation import Observation


class Prototype(object):
    """
    Prototype is used as a blueprint for OpenADMS workers.
    """

    def __init__(self, name, type, managers):
        self.logger = logging.getLogger(name)

        self._name = name   # Module name, e.g., 'serialPort'.
        self._type = type   # Class path, e.g., 'modules.port.SerialPort'.

        self._config_manager = managers.config_manager
        self._module_manager = managers.module_manager
        self._sensor_manager = managers.sensor_manager

        self._uplink = None
        self._is_running = True

        # A dictionary of the various payload data types and their respective
        # callback functions.  Further callback functions can be added with the
        # `add_handler()` method.
        self._handlers = {
            'observation': self.do_handle_observation,
            'service': self.do_handle_service
        }

    def add_handler(self,
                    data_type: str,
                    func: Callable[[Dict, Dict], None]) -> None:
        """Registers a callback function for handling of messages.
        
        Args:
            data_type (str): Name of the data type (observation, service, ...).
            func (Callable): Callback function for handling the message.        
        """
        self._handlers[data_type] = func

    def do_handle_observation(self, header: Dict, payload: Dict) -> None:
        """Handles an observation by forwarding it to the processing method and
        prepares the result for publishing."""
        obs = Observation(payload)

        if self._is_running:
            obs = self.process_observation(Observation(payload))

        if obs:
            self.publish_observation(obs)

    def do_handle_service(self, header: Dict, payload: Dict) -> None:
        """Processes service messages."""
        sender = header.get('from', '?')
        action = payload.get('action')

        if action is 'pause':
            self._is_running = False
            self.logger.info('Paused module "{}" by call from "{}"'
                             .format(self._name, sender))
        elif action is 'start':
            self._is_running = True
            self.logger.info('Started module "{}" by call from "{}"'
                             .format(self._name, sender))

    def handle(self, message: List[Dict]) -> None:
        """Processes messages by calling callback functions for data
        handling.

        Args:
            message (List): Header and payload of the message, both Dict.
        """
        if not self.is_sequence(message) or len(message) < 2:
            self.logger.warning('{}: received message is invalid'
                                .format(self._name))
            return

        header = message[0]
        payload = message[1]

        if not header or not payload:
            self.logger.warning('{}: received data is corrupted'
                                .format(self._name))
            return

        payload_type = header.get('type')

        if not payload_type:
            self.logger.error('{}: no payload type defined'.format(self._name))
            return

        handler_func = self._handlers.get(payload_type)

        if not handler_func:
            self.logger.warning('{}: no handler found for payload type "{}"'
                                .format(self._name, payload_type))
            return

        handler_func(header, payload)

    def is_sequence(self, arg: Any) -> bool:
        """Checks whether the argument is a list/a tuple or not."""
        return (not hasattr(arg, 'strip') and
                hasattr(arg, '__getitem__') or
                hasattr(arg, '__iter__'))

    def process_observation(self, obs: Type[Observation]) -> Observation:
        # Will be overwritten by the worker.
        pass

    def publish(self, target: str, header: Dict, payload: Dict) -> None:
        """Appends header and payload to a list, converts the list to a JSON
        string and sends it to the designated target by using the callback
        function `_uplink()`. The JSON string has the format:

            [ { <header> }, { <payload> } ].

        Args:
            target (str): The name of the target.
            header (Dict): The header of the message.
            payload (Dict): The payload of the message.
        """
        if not self._uplink:
            self.logger.error('No uplink defined for module "{}"'
                              .format(self._name))
            return

        try:
            message = json.dumps([header, payload])
            self._uplink(target, message)
        except TypeError:
            self.logger.error('Can\'t publish message '
                              '(header or payload invalid)')

    def publish_observation(self, obs: Type[Observation]) -> None:
        """Prepares the observation for publishing and forwards it to the
        messenger.

        Args:
            obs (Observation): Observation object.

        Returns:
            Observation object.
        """
        receivers = obs.get('receivers')
        index = obs.get('nextReceiver')

        # No receivers defined.
        if len(receivers) == 0:
            logging.debug('No receivers defined in observation "{}" '
                          'with ID "{}"'.format(obs.get('name'),
                                                obs.get('id')))
            return

        # No index defined.
        if (index is None) or (index < 0):
            self.logger.warning('Next receiver of observation "{}" with ID '
                                '"{}" not defined'.format(obs.get('name'),
                                                          obs.get('id')))
            return

        # Receivers list has been processed and observation is finished.
        if index >= len(receivers):
            self.logger.debug('Observation "{}" with ID "{}" has been finished'
                              .format(obs.get('name'),
                                      obs.get('id')))
            return

        # Name of the sending module.
        sender = receivers[index - 1]

        # Increase the receivers index.
        next_receiver = receivers[index]
        obs.set('nextReceiver', index + 1)

        # Create header and payload.
        header = {
            'from': sender,
            'type': 'observation'
        }

        payload = obs.data

        # Send the observation to the next module.
        self.publish(next_receiver, header, payload)

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def name(self) -> str:
        return self._name

    @property
    def type(self) -> str:
        return self._type

    @property
    def uplink(self) -> Callable[[str, str], None]:
        return self._uplink

    @is_running.setter
    def is_running(self, is_running: bool) -> None:
        self._is_running = is_running

    @type.setter
    def type(self, type: str) -> None:
        self._type = type

    @uplink.setter
    def uplink(self, uplink: Callable[[str, str], None]) -> None:
        self._uplink = uplink
