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

import copy
import datetime as dt
import logging
import threading
import time

logger = logging.getLogger('openadms')


class Scheduler(threading.Thread):

    def __init__(self, output_queue):
        threading.Thread.__init__(self)
        self.daemon = True
        self._output_queue = output_queue
        self._jobs = []

    def add(self, job):
        self._jobs.append(job)
        logger.debug('Added new job "{}" for sensor "{}" on port "{}" '
                     'to jobs list'.format(job.name,
                                           job.sensor.name,
                                           job.port_name))

    def cancel(self, job):
        self._jobs.remove(job)

    def clear(self):
        del self._jobs[:]

    def run(self):
        while True:
            if len(self._jobs) > 0:
                for job in self._jobs:
                    if not job.enabled:
                        # logger.debug('Skipping disabled job')
                        continue

                    if job.has_expired():
                        self.cancel(job)
                        continue

                    if job.is_pending():
                        job.run(self._output_queue)

            time.sleep(0.1)


class Job(object):

    def __init__(self, name, port_name, sensor, enabled, start_date, end_date,
        schedule):
        self._date_fmt = '%Y-%m-%d'
        self._time_fmt = '%H:%M:%S'

        self._name = name
        self._port_name = port_name
        self._sensor = sensor
        self._enabled = enabled

        # Convert date to date and time.
        self._start_date = self.get_datetime(start_date, self._date_fmt)
        self._end_date = self.get_datetime(end_date, self._date_fmt)

        self._schedule = schedule

    @property
    def enabled(self):
        return self._enabled

    def get_datetime(self, dt_str, dt_fmt):
        """Converts a date string to a time stamp."""
        return dt.datetime.strptime(dt_str, dt_fmt)

    def has_expired(self):
        now = dt.datetime.now()
        expired = False

        if now > self._end_date:
            expired = True
            logger.debug('Job has expired')

        return expired

    def is_pending(self):
        if not self._enabled:
            return False

        now = dt.datetime.now()

        # Are we within the date range of the job?
        if now >= self._start_date and now < self._end_date:
            # No days definied, go on.
            if len(self._schedule) == 0:
                return True

            # Name of the current day (e.g., "Monday").
            current_day = now.strftime('%A')

            # Ignore current day if it is not listed in the schedule.
            if current_day in self._schedule:
                # Time ranges of the current day.
                periods = self._schedule[current_day]

                # No given time range means the job should be executed
                # all day long.
                if len(periods) == 0:
                    return True

                # Check all time ranges of the current day.
                if len(periods) > 0:
                    for p in periods:
                        # Start and end time of the current day.
                        start_time = self.get_datetime(p['StartTime'],
                                                       self._time_fmt).time()
                        end_time = self.get_datetime(p['EndTime'],
                                                     self._time_fmt).time()

                        # Are we within the time range of the current day?
                        if now.time() >= start_time and \
                                now.time() < end_time:
                            return True

        return False

    def run(self, output_queue):
        observation_set = self._sensor.get_observation_set(self._name)

        logger.debug('Job is running observation set "{}" of sensor "{}" '
                     'on port "{}"'.format(self._name,
                                           self._sensor.name,
                                           self._port_name))

        for obs in observation_set:
            # Continue if observation is disabled.
            if not obs.get('Enabled'):
                continue

            # Disable the observation if it should run one time only (for
            # instance, for initialization purposes).
            if obs.get('Onetime'):
                obs.set('Enabled', False)

            # Make a deep copy since we don't want to do any changes to the
            # observation in our set.
            obs_copy = copy.deepcopy(obs)
            obs_copy.data['Receivers'].insert(0, self._port_name)

            sleep_time = obs_copy.get('SleepTime')

            # Put the observation into the output queue (fire and forget).
            output_queue.put(obs_copy)

            time.sleep(sleep_time)

    @property
    def name(self):
        return self._name

    @property
    def port_name(self):
        return self._port_name

    @property
    def sensor(self):
        return self._sensor
