# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2017, 2019.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""
Timeslots for channels.
"""
from collections import defaultdict
import itertools
from typing import List, Tuple, Union

from .channels import Channel
from .exceptions import PulseError


# pylint: disable=missing-return-doc


class Interval:
    """Time interval."""

    def __init__(self, begin: int, end: int):
        """Create an interval = (begin, end))

        Args:
            begin: begin time of this interval
            end: end time of this interval

        Raises:
            PulseError: when invalid time or duration is specified
        """
        if begin < 0:
            raise PulseError("Cannot create Interval with negative begin time")
        if end < 0:
            raise PulseError("Cannot create Interval with negative end time")
        if begin > end:
            raise PulseError("Cannot create Interval with time beginning after end")
        self._begin = begin
        self._end = end

    @property
    def begin(self):
        """Begin time of this interval."""
        return self._begin

    @property
    def end(self):
        """End time of this interval."""
        return self._end

    @property
    def duration(self):
        """Duration of this interval."""
        return self._end - self._begin

    def has_overlap(self, interval: 'Interval') -> bool:
        """Check if self has overlap with `interval`.

        Args:
            interval: interval to be examined

        Returns:
            bool: True if self has overlap with `interval` otherwise False
        """
        if self.begin < interval.end and interval.begin < self.end:
            return True
        return False

    def shift(self, time: int) -> 'Interval':
        """Return a new interval shifted by `time` from self

        Args:
            time: time to be shifted

        Returns:
            Interval: interval shifted by `time`
        """
        return Interval(self.begin + time, self.end + time)

    def __eq__(self, other):
        """Two intervals are the same if they have the same begin and end.

        Args:
            other (Interval): other Interval

        Returns:
            bool: are self and other equal.
        """
        if self.begin == other.begin and self.end == other.end:
            return True
        return False

    def ends_before(self, other):
        """Whether intervals ends at time less than or equal to the
        other interval's starting time.

        Args:
            other (Interval): other Interval

        Returns:
            bool: are self and other equal.
        """
        if self.end <= other.begin:
            return True
        return False

    def starts_after(self, other):
        """Whether intervals starts at time greater than or equal to the
        other interval's ending time.

        Args:
            other (Interval): other Interval

        Returns:
            bool: are self and other equal.
        """
        if self.begin >= other.end:
            return True
        return False

    def __lt__(self, other):
        """If interval ends before other interval.

        Args:
            other (Interval): other Interval

        Returns:
            bool: are self and other equal.
        """
        return self.ends_before(other)

    def __gt__(self, other):
        """Interval is greater than other if it starts at a time less than or equal to the
        other interval's ending time.

        Args:
            other (Interval): other Interval

        Returns:
            bool: are self and other equal.
        """
        return self.starts_after(other)

    def __repr__(self):
        """Return a readable representation of Interval Object"""
        return "{}({}, {})".format(self.__class__.__name__, self.begin, self.end)


class Timeslot:
    """Named tuple of (Interval, Channel)."""

    def __init__(self, interval: Interval, channel: Channel):
        self._interval = interval
        self._channel = channel

    @property
    def interval(self):
        """Interval of this time slot."""
        return self._interval

    @property
    def channel(self):
        """Channel of this time slot."""
        return self._channel

    def shift(self, time: int) -> 'Timeslot':
        """Return a new Timeslot shifted by `time`.

        Args:
            time: time to be shifted
        """
        return Timeslot(self.interval.shift(time), self.channel)

    def __eq__(self, other) -> bool:
        """Two time-slots are the same if they have the same interval and channel.

        Args:
            other (Timeslot): other Timeslot
        """
        if self.interval == other.interval and self.channel == other.channel:
            return True
        return False

    def __repr__(self):
        """Return a readable representation of Timeslot Object"""
        return "{}({}, {})".format(self.__class__.__name__,
                                   self.channel,
                                   (self.interval.begin, self.interval.end))


class TimeslotCollection:
    """Collection of `Timeslot`s."""

    def __init__(self, *timeslots: Union[Timeslot, 'TimeslotCollection']):
        """Create a new time-slot collection.

        Args:
            *timeslots: list of time slots
        Raises:
            PulseError: when overlapped time slots are specified
        """
        self._table = defaultdict(list)

        for timeslot in timeslots:
            if isinstance(timeslot, TimeslotCollection):
                self._merge_timeslot_collection(timeslot)
            else:
                self._merge_timeslot(timeslot)

    @property
    def timeslots(self) -> Tuple[Timeslot]:
        """Sorted tuple of `Timeslot`s in collection."""
        return tuple(itertools.chain.from_iterable(self._table.values()))

    @property
    def channels(self) -> Tuple[Timeslot]:
        """Channels within the timeslot collection."""
        return tuple(k for k, v in self._table.items() if v)

    @property
    def start_time(self) -> int:
        """Return earliest start time in this collection."""
        return self.ch_start_time(*self.channels)

    @property
    def stop_time(self) -> int:
        """Return maximum time of timeslots over all channels."""
        return self.ch_stop_time(*self.channels)

    @property
    def duration(self) -> int:
        """Return maximum duration of timeslots over all channels."""
        return self.stop_time

    def _merge_timeslot_collection(self, other: 'TimeslotCollection'):
        """Mutably merge timeslot collections into this TimeslotCollection.

        Args:
            other: TimeSlotCollection to merge
        """
        common_channels = set(self.channels) & set(other.channels)

        for channel in other.channels:
            ch_timeslots = self._table[channel]
            other_ch_timeslots = other._table[channel]
            # if channel is in self there might be an overlap
            timeslot_idx = 0
            if channel in common_channels:
                for other_ch_timeslot in other_ch_timeslots:
                    insert_idx = self._merge_timeslot(other_ch_timeslot)

                    timeslot_idx += 1
                    # timeslot was inserted at end of list. Remaining timeslots can be appended.
                    if insert_idx == len(self._table[channel]) - 1:
                        break

                ch_to_append = other_ch_timeslots[timeslot_idx:]

            # otherwise directly insert
            else:
                ch_to_append = other_ch_timeslots

            if ch_to_append:
                ch_timeslots += ch_to_append

    def _merge_timeslot(self, timeslot: Timeslot) -> int:
        """Mutably merge timeslots into this TimeslotCollection.

        Note timeslots are sorted internally on their respective channel

        Args:
            timeslot: Timeslot to merge

        Returns:
            int: Return the index in which timeslot was inserted

        Raises:
            PulseError: If timeslots overlap
        """
        interval = timeslot.interval
        ch_timeslots = self._table[timeslot.channel]

        insert_idx = len(ch_timeslots)

        # bubble sort for insertion location.
        # Worst case O(n_channels), O(1) for append
        # could be improved by implementing interval tree
        for ch_timeslot in reversed(ch_timeslots):
            ch_interval = ch_timeslot.interval

            if interval > ch_interval:
                break
            elif interval.has_overlap(ch_interval):
                raise PulseError("Timeslot: {0} overlaps with existing"
                                 "Timeslot: {1}".format(timeslot, ch_timeslot))

            insert_idx -= 1

        ch_timeslots.insert(insert_idx, timeslot)

        return insert_idx

    def ch_timeslots(self, channel: Channel) -> Tuple[Timeslot]:
        """Sorted tuple of `Timeslot`s for channel in this TimeslotCollection."""
        if channel in self._table:
            return tuple(self._table[channel])

        return tuple()

    def ch_start_time(self, *channels: List[Channel]) -> int:
        """Return earliest start time in this collection.

        Args:
            *channels: Channels over which to obtain start_time.
        """
        timeslots = list(itertools.chain(*(self._table[chan] for chan in channels
                                           if chan in self._table)))
        if timeslots:
            return min(timeslot.interval.begin for timeslot in timeslots)

        return 0

    def ch_stop_time(self, *channels: List[Channel]) -> int:
        """Return maximum time of timeslots over all channels.

        Args:
            *channels: Channels over which to obtain stop time.
        """
        timeslots = list(itertools.chain(*(self._table[chan] for chan in channels
                                           if chan in self._table)))
        if timeslots:
            return max(timeslot.interval.end for timeslot in timeslots)

        return 0

    def ch_duration(self, *channels: List[Channel]) -> int:
        """Return maximum duration of timeslots over all channels.

        Args:
            *channels: Channels over which to obtain the duration.
        """
        return self.ch_stop_time(*channels)

    def is_mergeable_with(self, timeslot_collection: 'TimeslotCollection') -> bool:
        """Return if self is mergeable with `timeslots`.

        Args:
            timeslot_collection: TimeslotCollection to be checked for mergeability
        """
        common_channels = set(self.channels) & set(timeslot_collection.channels)

        for channel in common_channels:
            ch_timeslots = self._table[channel]
            other_ch_timeslots = timeslot_collection._table[channel]

            for other_ch_timeslot in other_ch_timeslots:
                other_ch_interval = other_ch_timeslot.interval

                append = True
                for ch_timeslot in ch_timeslots:
                    ch_interval = ch_timeslot.interval
                    if other_ch_interval > ch_interval:
                        break
                    if ch_interval.has_overlap(other_ch_interval):
                        return False

                    append = False

                # since timeslots are sorted along channel
                # if instruction can be appended, all other instructions on channel
                # can be appended.
                if append:
                    break

        return True

    def merge(self, timeslots: 'TimeslotCollection') -> 'TimeslotCollection':
        """Return a new TimeslotCollection with `timeslots` merged into it.

        Args:
            timeslots: TimeslotCollection to be merged
        """
        return TimeslotCollection(self, timeslots)

    def shift(self, time: int) -> 'TimeslotCollection':
        """Return a new TimeslotCollection shifted by `time`.

        Args:
            time: time to be shifted by
        """
        slots = [Timeslot(slot.interval.shift(time), slot.channel) for slot in self.timeslots]
        return TimeslotCollection(*slots)

    def __eq__(self, other) -> bool:
        """Two time-slot collections are the same if they have the same time-slots.

        Args:
            other (TimeslotCollection): other TimeslotCollection
        """
        if set(self.channels) == set(other.channels):
            for channel in self.channels:
                if self.ch_timeslots(channel) != self.ch_timeslots(channel):
                    return False
            return True
        return False

    def __repr__(self):
        """Return a readable representation of TimeslotCollection Object"""
        rep = dict()
        for key, val in self._table.items():
            rep[key] = [(timeslot.interval.begin, timeslot.interval.end) for timeslot in val]
        return self.__class__.__name__ + str(rep)
