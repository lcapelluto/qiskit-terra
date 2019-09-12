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
Channels.
"""
from abc import ABCMeta

from qiskit.pulse.exceptions import PulseError


class Channel(metaclass=ABCMeta):
    """Base class of channels."""

    prefix = None

    def __init__(self, index: int, buffer: int = 0):
        """Channel class.

        Args:
            index: Index of channel. Channels in Pulse map arbitrarily to qubit index
            buffer: Buffer that should be placed between instructions on channel

        Raises:
            PulseError: If integer index or buffer not supplied
        """
        if not isinstance(index, int):
            raise PulseError('Channel index must be integer')

        self._index = index

        if not isinstance(buffer, int):
            raise PulseError('Channel buffer must be integer')

        self._buffer = buffer

    @property
    def index(self) -> int:
        """Return the index of this channel."""
        return self._index

    @property
    def buffer(self) -> int:
        """Return the buffer for this channel."""
        return self._buffer

    @property
    def name(self) -> str:
        """Return the name of this channel."""
        return '%s%d' % (self.__class__.prefix, self._index)

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, self._index)

    def __eq__(self, other: 'Channel') -> bool:
        """Return True iff this and other are of the same type, and have the same index."""
        return type(self) is type(other) and self._index == other._index

    def __hash__(self):
        return hash((type(self), self._index))


class PulseChannel(Channel, metaclass=ABCMeta):
    """Base class of Channel supporting pulse output."""
    pass


class DriveChannel(PulseChannel):
    """Drive Channel."""
    prefix = 'd'


class MeasureChannel(PulseChannel):
    """Measure Channel."""
    prefix = 'm'


class ControlChannel(PulseChannel):
    """Control Channel."""
    prefix = 'u'


class AcquireChannel(Channel):
    """Acquire channel."""
    prefix = 'a'


class SnapshotChannel(Channel):
    """Snapshot channel."""
    prefix = 's'

    def __init__(self):
        """Create new snapshot channel."""
        super().__init__(0)


class MemorySlot(Channel):
    """Memory slot channel."""
    prefix = 'm'


class RegisterSlot(Channel):
    """Classical resister slot channel."""
    prefix = 'c'
