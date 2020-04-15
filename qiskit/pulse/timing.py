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

"""Private utility methods used by Schedules."""

from copy import copy
from typing import List, Tuple

from .exceptions import PulseError

Interval = Tuple[int, int]


class Timeslots:
    """"""

    def __init__(self):
        """"""
        self._timeslots = {}

    def add_timeslots(self, time: int, new_timeslots: 'Timeslots') -> None:
        """Update all time tracking within this schedule based on the given schedule.

        Args:
            time: The time to insert the schedule into self.
            schedule: The schedule to insert into self.

        Raises:
            PulseError: If timeslots overlap.
        """
        for key in new_timeslots.keys():

            if key not in self._timeslots:
                if time == 0:
                    self._timeslots[key] = copy(new_timeslots[key])
                else:
                    self._timeslots[key] = [(i[0] + time, i[1] + time)
                                                for i in new_timeslots[key]]
                continue

            for idx, interval in enumerate(new_timeslots[key]):
                if interval[0] + time >= self._timeslots[key][-1][1]:
                    # Can append the remaining intervals
                    self._timeslots[key].extend(
                        [(i[0] + time, i[1] + time)
                         for i in new_timeslots[key][idx:]])
                    break

                try:
                    interval = (interval[0] + time, interval[1] + time)
                    index = _insertion_index(self._timeslots[key], interval)
                    self._timeslots[key].insert(index, interval)
                except PulseError:
                    raise PulseError(
                        "Cannot merge schedules at time {time} because its instruction on channel {key} "
                        "scheduled from time {t0} to {tf} overlaps with an existing instruction."
                        "".format(time=time, key=key, t0=interval[0], tf=interval[1]))

    def keys(self):
        return self._timeslots.keys()

    def __getitem__(self, key):
        return self._timeslots[key]

    def __contains__(self, key):
        return key in self._timeslots


def _insertion_index(intervals: List[Interval], new_interval: Interval, index: int = 0) -> int:
    """
    Using binary search on start times, return the index into `intervals` where the new interval
    belongs, or raise an error if the new interval overlaps with any existing ones.
    Args:
        intervals: A sorted list of non-overlapping Intervals.
        new_interval: The interval for which the index into intervals will be found.
        index: A running tally of the index, for recursion. The user should not pass a value.
    Returns:
        The index into intervals that new_interval should be inserted to maintain a sorted list
        of intervals.
    Raises:
        PulseError: If new_interval overlaps with the given intervals.
    """
    if not intervals:
        return index
    if len(intervals) == 1:
        if _overlaps(intervals[0], new_interval):
            raise PulseError("New interval overlaps with existing.")
        return index if new_interval[0] < intervals[0][0] else index + 1

    mid_idx = len(intervals) // 2
    if new_interval[0] < intervals[mid_idx][0]:
        return _insertion_index(intervals[:mid_idx], new_interval, index=index)
    else:
        return _insertion_index(intervals[mid_idx:], new_interval, index=index + mid_idx)


def _overlaps(first: Interval, second: Interval) -> bool:
    """
    Return True iff first and second overlap.
    Note: first.stop may equal second.start, since Interval stop times are exclusive.
    """
    if first[0] == second[0] == second[1]:
        # They fail to overlap if one of the intervals has duration 0
        return False
    if first[0] > second[0]:
        first, second = second, first
    return second[0] < first[1]
