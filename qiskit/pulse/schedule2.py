# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2019.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Schedule."""

import abc
import warnings

from collections import defaultdict, namedtuple
from typing import List, Tuple, Iterable, Union, Dict, Callable, Set, Optional, Type

from .channels import Channel
from .commands import Command
from .exceptions import PulseError

# pylint: disable=missing-return-doc


ScheduleDatum = namedtuple('ScheduleDatum',
                           ['time',       # int 
                            'schedule'])  # Union[CommandSchedule, Schedule]


CommandSchedule = namedtuple('CommandSchedule', ['command', 'channel'])


Interval = namedtuple('Interval', ['start', 'stop'])


class Schedule():
    """"""
    # pylint: disable=missing-type-doc
    def __init__(self, *schedules: List[Union['Schedule', Tuple[int, 'Schedule']]],
                 name: Optional[str] = None):
        """Create empty schedule.

        Args:
            *schedules: Child Schedules of this parent Schedule. May either be passed as
                the list of schedules, or a list of (start_time, schedule) pairs
            name: Name of this schedule

        Raises:
            PulseError: If timeslots intercept.
        """
        self._name = name
        self._timeslots = defaultdict(list)  # Dict[Channel: List[Interval]]
        self._duration = 0  # TODO
        self._buffer = 0  # TODO
        self._data = []  # List[ScheduleDatum]
        for sched in schedules:
            self.insert(0, sched)  # so slow

    @property
    def name(self) -> str:
        return self._name

    @property
    def buffer(self) -> int:
        return self._buffer

    @property
    def duration(self) -> int:
        return self._duration

    @property
    def channels(self) -> Tuple[Channel]:
        """Returns channels that this schedule uses."""
        # TODO This can be made faster
        return tuple(self._timeslots.keys())

    def ch_start_time(self, *channels: List[Channel]) -> int:
        """Return minimum start time over supplied channels.

        Args:
            *channels: Supplied channels
        """
        try:
            return min([self._timeslots[channel][0].start for channel in channels])
        except IndexError:
            return 0

    def ch_stop_time(self, *channels: List[Channel]) -> int:
        """Return maximum time over supplied channels.

        Args:
            *channels: Supplied channels
        """
        max_stop = 0
        for intervals in [self._timeslots[channel] for channel in channels]:
            if intervals:
                max_stop = max(intervals[-1].stop, max_stop)
            # return max([self._timeslots[channel][-1].stop for channel in channels])
        return max_stop

    @property
    def instructions(self) -> Tuple[Tuple[int, 'ScheduleDatum'], ...]:  #??
        """Get time-ordered instructions from Schedule tree."""
        insts = []
        for time, schedule in self._data:
            if isinstance(schedule, CommandSchedule):
                insts.append((time, schedule))
            else:
                for inst_time, inst in schedule.instructions:
                    insts.append((time + inst_time), inst)
        return insts

    def shift(self, time: int, name: Optional[str] = None) -> 'Schedule':
        """Return a new schedule shifted forward by `time`.

        Args:
            time: Time to shift by
            name: Name of the new schedule. Defaults to name of self
        """
        sched = Schedule(name=self.name)
        for inst_time, inst_sched in self._data:
            sched.insert(time + inst_time, inst_sched.command, inst_sched.channel)
        return sched

    def insert(self, start_time: int, command: Command, channel: Channel,
               schedule: 'Schedule' = None, buffer: bool = False,
               name: Optional[str] = None) -> 'Schedule':
        """Return a new schedule with `schedule` inserted within `self` at `start_time`.

        Args:
            start_time: Time to insert the schedule
            schedule: Schedule to insert
            buffer: Whether to obey buffer when inserting
            name: Name of the new schedule. Defaults to name of self
        """
        # TODO dont modify
        sched = CommandSchedule(command=command, channel=channel)
        stop_time = start_time + command.duration

        # TODO cannot append
        self._timeslots[channel].append(Interval(start=start_time, stop=stop_time))

        self._duration = max(self.duration, stop_time)
        sched_datum = ScheduleDatum(time=start_time, schedule=sched)
        self._data.append(sched_datum)

    def append(self, command: Command, channel: Channel, buffer: bool = True,
               name: Optional[str] = None) -> 'Schedule':
        r"""Return a new schedule with `schedule` inserted at the maximum time over
        all channels shared between `self` and `schedule`.

       $t = \textrm{max}({x.stop\_time |x \in self.channels \cap schedule.channels})$

        Args:
            schedule: schedule to be appended
            buffer: Whether to obey buffer when appending
            name: Name of the new schedule. Defaults to name of self
        """
        # TODO dont modify
        sched = CommandSchedule(command=command, channel=channel)
        start_time = self.ch_stop_time(channel)
        stop_time = start_time + command.duration
        self._timeslots[channel].append(Interval(start=start_time, stop=stop_time))
        self._duration = max(self.duration, stop_time)
        sched_datum = ScheduleDatum(time=start_time, schedule=sched)
        self._data.append(sched_datum)

    def flatten(self) -> 'Schedule':
        """Return a new schedule which is the flattened schedule contained all `instructions`."""
        sched = Schedule(self.name)
        for time, inst in self.instructions:
            sched.insert(time, inst)
        return sched

    def __eq__(self, other: 'Schedule') -> bool:
        """Test if two Schedules are equal.

        Equality is checked by verifying there is an equal instruction at every time
        in `other` for every instruction in this Schedule.

        Warning: This does not check for logical equivalencly. Ie.,
            ```python
            >>> (Delay(10)(DriveChannel(0)) + Delay(10)(DriveChannel(0)) ==
                 Delay(20)(DriveChannel(0)))
            False
            ```
        """
        pass

    def __add__(self, other: 'Schedule') -> 'Schedule':
        """Return a new schedule with `other` inserted within `self` at `start_time`."""
        pass

    def __or__(self, other: 'Schedule') -> 'Schedule':
        """Return a new schedule which is the union of `self` and `other`."""
        pass

    def __lshift__(self, time: int) -> 'Schedule':
        """Return a new schedule which is shifted forward by `time`."""
        pass

    def __repr__(self):
        res = 'Schedule("name=%s", ' % self._name if self._name else 'Schedule('
        instructions = [repr(instr) for instr in self.instructions]
        res += ', '.join([str(i) for i in instructions[:50]])
        if len(instructions) > 50:
            return res + ', ...)'
        return res + ')'

    @property
    def timeslots(self) -> Dict[Channel, Interval]:
        warnings.warn("The timeslots property is becoming private. Do not try to access it in the "
                      "future.", DeprecationWarning)
        return self._timeslots

    @property
    def start_time(self) -> int:
        warnings.warn("start_time is deprecated, Schedules start at time 0.",
                      DeprecationWarning)
        return 0

    @property
    def stop_time(self) -> int:
        warnings.warn("stop_time is deprecated, use duration instead.",
                      DeprecationWarning)
        return self.duration

    def ch_duration(self, *channels: List[Channel]) -> int:
        """Return duration of schedule over supplied channels.

        Args:
            *channels: Supplied channels
        """
        warnings.warn("ch_duration is deprecated, use ch_stop_time instead.",
                      DeprecationWarning)
        return self.ch_stop_time(channels)

    def union(self, *schedules: Union['Schedule', Tuple[int, 'Schedule']],
              name: Optional[str] = None) -> 'Schedule':
        """Return a new schedule which is the union of both `self` and `schedules`.

        Args:
            *schedules: Schedules to be take the union with this `Schedule`.
            name: Name of the new schedule. Defaults to name of self
        """
        warnings.warn("The union method is being deprecated. Please use append_by_channel "
                      "instead.", DeprecationWarning)











class ParameterizedSchedule:
    """Temporary parameterized schedule class.

    This should not be returned to users as it is currently only a helper class.

    This class is takes an input command definition that accepts
    a set of parameters. Calling `bind` on the class will return a `Schedule`.

    # TODO: In the near future this will be replaced with proper incorporation of parameters
        into the `Schedule` class.
    """

    def __init__(self, *schedules, parameters: Optional[Dict[str, Union[float, complex]]] = None,
                 name: Optional[str] = None):
        full_schedules = []
        parameterized = []
        parameters = parameters or []
        self.name = name or ''
        # partition schedules into callable and schedules
        for schedule in schedules:
            if isinstance(schedule, ParameterizedSchedule):
                parameterized.append(schedule)
                parameters += schedule.parameters
            elif callable(schedule):
                parameterized.append(schedule)
            elif isinstance(schedule, Schedule):
                full_schedules.append(schedule)
            else:
                raise PulseError('Input type: {0} not supported'.format(type(schedule)))

        self._parameterized = tuple(parameterized)
        self._schedules = tuple(full_schedules)
        self._parameters = tuple(sorted(set(parameters)))

    @property
    def parameters(self) -> Tuple[str]:
        """Schedule parameters."""
        return self._parameters

    def bind_parameters(self, *args: List[Union[float, complex]],
                        **kwargs: Dict[str, Union[float, complex]]) -> Schedule:
        """Generate the Schedule from params to evaluate command expressions"""
        bound_schedule = Schedule(name=self.name)
        schedules = list(self._schedules)

        named_parameters = {}
        if args:
            for key, val in zip(self.parameters, args):
                named_parameters[key] = val
        if kwargs:
            for key, val in kwargs.items():
                if key in self.parameters:
                    if key not in named_parameters.keys():
                        named_parameters[key] = val
                    else:
                        raise PulseError("%s got multiple values for argument '%s'"
                                         % (self.__class__.__name__, key))
                else:
                    raise PulseError("%s got an unexpected keyword argument '%s'"
                                     % (self.__class__.__name__, key))

        for param_sched in self._parameterized:
            # recursively call until based callable is reached
            if isinstance(param_sched, type(self)):
                predefined = param_sched.parameters
            else:
                # assuming no other parametrized instructions
                predefined = self.parameters
            sub_params = {k: v for k, v in named_parameters.items() if k in predefined}
            schedules.append(param_sched(**sub_params))

        # construct evaluated schedules
        for sched in schedules:
            bound_schedule |= sched

        return bound_schedule

    def __call__(self, *args: List[Union[float, complex]],
                 **kwargs: Dict[str, Union[float, complex]]) -> Schedule:
        return self.bind_parameters(*args, **kwargs)
