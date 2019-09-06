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

"""
This object provides an efficient, centralized interface for extracting backend information useful
to building Pulse schedules, streamlining this part of our schedule building workflow. It is
important to note that the resulting `Schedule` and its execution are not constrainted by the
SystemInfo. For constraint validation, see the `validate.py` module (coming soon).

Questions about the backend which can be answered by SystemInfo and are likely to come up when
building schedules include:
  - What is the topology of this backend?
  - What characteristics (e.g. T1, T2) do the qubits on this backend have?
  - What is the time delta between signal samples (`dt`) on this backend?
  - What channel should be used to drive qubit 0?
  - What are the defined native gates on this backend?
"""
import datetime
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, Union

from qiskit.qobj.converters import QobjToInstructionConverter
from qiskit.util import _to_tuple

from qiskit.pulse.channels import (Channel, DriveChannel, MeasureChannel, ControlChannel,
                                   AcquireChannel)
from qiskit.pulse.exceptions import PulseError
from qiskit.pulse.schedule import Schedule, ParameterizedSchedule

# pylint: disable=missing-return-doc
# Questions
#   - CmdDef should be separate so that backend can be required?
#   - Memoize? Or make QobjToInstructionConverter faster?
#   - __getattr__ and get_property are not stable, and should also have more tests


class SystemInfo():
    """A resource for getting information from a backend, tailored for Pulse users."""

    def __init__(self,
                 backend: ['BaseBackend']):
        """
        Initialize a SystemInfo instance with the data from the backend.

        Args:
            backend: A Pulse enabled backend returned by a Qiskit provider.
            default_ops: {(op_name, *qubits): `Schedule` or `ParameterizedSchedule`}
        """
        if not backend.configuration().open_pulse:
            raise PulseError("The backend '{}' is not enabled "
                             "with OpenPulse.".format(backend.name()))
        self._backend = backend
        self._backend_props = backend.properties()
        self._defaults = backend.defaults()
        self._config = backend.configuration()

    @property
    def dt(self) -> float:
        """Time delta between samples on the signal channels in seconds."""
        return self._config.dt * 1.e-9

    @property
    def dtm(self) -> float:
        """Time delta between samples on the acquisition channels in seconds."""
        return self._config.dtm * 1e-9

    @property
    def sample_rate(self) -> float:
        """Sample rate of the signal channels in Hz (1/dt)."""
        return 1.0 / self.dt

    def hamiltonian(self) -> str:
        """
        Return the LaTeX Hamiltonian string for this device and print its description if
        provided.

        Raises:
            PulseError: If the hamiltonian is not defined.
        """
        ham = self._config.hamiltonian.get('h_latex')
        if ham is None:
            raise PulseError("Hamiltonian not found.")
        print(self._config.hamiltonian.get('description'))
        return ham

    def drives(self, qubit: int) -> DriveChannel:
        """
        Return the drive channel for the given qubit.

        Raises:
            PulseError: If the qubit is not a part of the system.
        """
        if qubit > self._config.n_qubits:
            raise PulseError("This system does not have {} qubits.".format(qubit))
        return DriveChannel(qubit)

    def measures(self, qubit: int) -> MeasureChannel:
        """
        Return the measure stimulus channel for the given qubit.

        Raises:
            PulseError: If the qubit is not a part of the system.
        """
        if qubit > self._config.n_qubits:
            raise PulseError("This system does not have {} qubits.".format(qubit))
        return MeasureChannel(qubit)

    def acquires(self, qubit: int) -> AcquireChannel:
        """
        Return the acquisition channel for the given qubit.

        Raises:
            PulseError: If the qubit is not a part of the system.
        """
        if qubit > self._config.n_qubits:
            raise PulseError("This system does not have {} qubits.".format(qubit))
        return AcquireChannel(qubit)

    def controls(self, qubit: int) -> ControlChannel:
        """
        Return the control channel for the given qubit.

        Raises:
            PulseError: If the qubit is not a part of the system.
        """
        # TODO: It's probable that controls can't map trivially to qubits.
        if qubit > self._config.n_qubits:
            raise PulseError("This system does not have {} qubits.".format(qubit))
        return ControlChannel(qubit)

    def draw(self) -> None:
        """
        Visualize the topology of the device, showing qubits, their interconnections, and the
        channels which interact with them. Optionally print a listing of the supported 1Q and
        2Q gates.
        """
        # TODO: Implement the draw method.
        raise NotImplementedError

    def __str__(self) -> str:
        if not self._backend:
            return object.__str__(self)
        return '{}({} qubit{} operating on {})'.format(
            self.name,
            self._config.n_qubits,
            's' if self._config.n_qubits > 1 else '',
            self.basis_gates)

    def __repr__(self) -> str:
        if not self._backend:
            return object.__repr__(self)
        ops = {op: qubs.keys() for op, qubs in self._ops_definition.items()}
        ham = self._config.hamiltonian.get('description') if self._config.hamiltonian else ''
        return ("{}({} {}Q\n    Operations:\n{}\n    Properties:\n{}\n    Configuration:\n{}\n"
                "    Hamiltonian:\n{})".format(self.__class__.__name__,
                                               self.name,
                                               self._config.n_qubits,
                                               ops,
                                               list(self._properties.__dict__.keys()),
                                               list(self._config.__dict__.keys()),
                                               ham))

    def __getattr__(self, attr: str) -> Any:
        """
        Capture undefined attribute lookups and interpret it as an operation
        lookup.
            For example:
                system.x(0) <=> system.get(`x', qubit=0)
        Capture undefined attribute lookups and interpret them as backend
        properties.
            For example:
                system.backend_name <=> system.get_property(backend_name)
                system.t1(0) <=> system.get_property('t1', 0)
        """
        # FIXME
        if self._backend is None:
            raise PulseError("Please instantiate the SystemInfo with a backend to get this "
                             "information.")

        def fancy_get(qubits: Union[int, Iterable[int]] = None,
                      *params: List[Union[int, float, complex]],
                      **kwparams: Dict[str, Union[int, float, complex]]):
            try:
                qubits = _to_tuple(qubits)
                return self._defaults.get(attr, qubits, *params, **kwparams)
            except PulseError:
                try:
                    return self.get_property(attr, *params, error=True)
                except PulseError:
                    raise AttributeError("{} object has no attribute "
                                         "'{}'".format(self.__class__.__name__, attr))
        return fancy_get
