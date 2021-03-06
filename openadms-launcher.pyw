#!/usr/bin/env python3.6

"""OpenADMS Node Graphical Launcher

This Python script starts OpenADMS Node by using a graphical launcher. You have
to install the Python modules `wxPython` and `Gooey` with pip at first::

    $ pipenv install Gooey

For more information, please visit https://www.dabamos.de/.
"""

__author__ = 'Philipp Engel'
__copyright__ = 'Copyright (c) 2017 Hochschule Neubrandenburg'
__license__ = 'BSD-2-Clause'

import argparse
import logging
import signal
import sys

from gooey import Gooey, GooeyParser

from core.system import System
from openadms import (exception_hook, main, setup_logging,
                      setup_thread_exception_hook, sighup_handler,
                      sigint_handler, start_mqtt_message_broker, valid_path)

logger = logging.getLogger()


@Gooey(advanced=True,
       language='english',
       program_name=('OpenADMS Node {} - '
                     'Open Automatic Deformation Monitoring System'
                     .format(System.get_openadms_version())),
       default_size=(610, 580),
       monospace_display=True,
       image_dir='./extra')
def mainw() -> None:
    """Wrapper routine to run OpenADMS Node windowed."""
    parser = GooeyParser(
        description='OpenADMS Node {} - Open Automatic Deformation Monitoring '
                    'System'.format(System.get_openadms_version()))

    parser.add_argument('-c', '--config',
                        metavar='Configuration File',
                        help='Path to the configuration file',
                        dest='config_file_path',
                        action='store',
                        default='./config/config.json',
                        required=True,
                        widget='FileChooser')
    parser.add_argument('-v', '--verbosity',
                        metavar='Verbosity Level (1 - 9)',
                        help='Log more diagnostic messages',
                        dest='verbosity',
                        action='count',
                        default=6)
    parser.add_argument('-d', '--debug',
                        metavar='Debug',
                        help='Print debug messages',
                        dest='is_debug',
                        action='store_true',
                        default=False)
    parser.add_argument('-m', '--with-mqtt-broker',
                        metavar='MQTT',
                        help='Run internal MQTT message broker',
                        dest='is_mqtt_broker',
                        action='store_true',
                        default=True)
    parser.add_argument('-l', '--log-file',
                        metavar='Log File',
                        help='Path to log file',
                        dest='log_file',
                        action='store',
                        default='openadms.log',
                        widget='FileChooser')
    parser.add_argument('-b', '--bind',
                        metavar='Host',
                        help='IP address or FQDN of MQTT message broker',
                        dest='host',
                        action='store',
                        default='127.0.0.1')
    parser.add_argument('-p', '--port',
                        metavar='Port',
                        help='Port of MQTT message broker',
                        dest='port',
                        action='store',
                        type=int,
                        default=1883)
    args = parser.parse_args()

    try:
        valid_path(args.config_file_path)
    except argparse.ArgumentTypeError as e:
        logger.error(e)
        return

    setup_logging(args.is_debug, args.verbosity, args.log_file)

    # Use internal MQTT message broker (HBMQTT).
    if args.is_mqtt_broker:
        start_mqtt_message_broker(args.host, args.port)

    main(args.config_file_path)


if __name__ == '__main__':
    setup_thread_exception_hook()
    sys.excepthook = exception_hook

    # Use signal handlers to quit gracefully and restart on SIGHUP.
    signal.signal(signal.SIGINT, sigint_handler)

    if not System.is_windows():
        signal.signal(signal.SIGINT, sighup_handler)

    # Run wrapper.
    mainw()
