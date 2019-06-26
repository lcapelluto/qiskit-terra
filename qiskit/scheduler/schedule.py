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
Convenience entry point into pulse scheduling, requiring only a circuit and a backend. For more
control over pulse scheduling, look at `.schedule_circuit`.
"""
from typing import List, Optional, Union

from qiskit.circuit.quantumcircuit import QuantumCircuit
from qiskit.providers.basebackend import BaseBackend
from qiskit.pulse.cmd_def import CmdDef
from qiskit.pulse.schedule import Schedule

from qiskit.scheduler.schedule_circuit import schedule_circuit
from qiskit.scheduler.models import ScheduleConfig


def schedule(circuits: Union[QuantumCircuit, List[QuantumCircuit]],
             backend: BaseBackend,
             method: Optional[Union[str, List[str]]] = None) -> Schedule:
    """
    Schedule a circuit to a pulse Schedule, using the backend, according to any specified methods.
    Supported methods are documented in
    :py:func:`qiskit.pulse.scheduler.schedule_circuit.schedule_circuit`.

    Args:
        circuits: The quantum circuit or circuits to translate
        backend: A backend instance, which contains hardware specific data required for scheduling
        method: Optionally specify a particular scheduling method
    Returns:
        Schedule corresponding to the input circuit
    """
    defaults = backend.defaults()
    schedule_config = ScheduleConfig(
        cmd_def=CmdDef.from_defaults(defaults.cmd_def, defaults.pulse_library),
        meas_map=backend.configuration().meas_map)
    circuits = circuits if isinstance(circuits, list) else [circuits]
    schedules = [schedule_circuit(circuit, schedule_config, method) for circuit in circuits]
    return schedules[0] if len(schedules) == 1 else schedules
