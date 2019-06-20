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

"""QuantumCircuit to Pulse scheduler."""

from qiskit.circuit.quantumcircuit import QuantumCircuit
from qiskit.pulse.schedule import Schedule

from qiskit.scheduler.models import ScheduleConfig
from qiskit.scheduler.methods.basic import greedy_schedule, minimize_earliness_schedule


def schedule_circuit(circuit: QuantumCircuit,
                     schedule_config: ScheduleConfig,
                     methods) -> Schedule:
    """
    Basic scheduling pass from a circuit to a pulse Schedule, using the backend. By default, pulses
    are scheduled to occur as late as possible.

    Args:
        circuit: The quantum circuit to translate
        schedule_config: Backend specific parameters used for building the Schedule
        methods: TODO
    Returns:
        Schedule corresponding to the input circuit
    """
    if methods:
        return greedy_schedule(circuit, schedule_config)
    return minimize_earliness_schedule(circuit, schedule_config)
