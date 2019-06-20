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
control over pulse scheduling, look at .schedule_circuit
"""

from qiskit.circuit.quantumcircuit import QuantumCircuit
from qiskit.providers.basebackend import BaseBackend
from qiskit.pulse.cmd_def import CmdDef
from qiskit.pulse.schedule import Schedule

from qiskit.scheduler.schedule_circuit import schedule_circuit
from qiskit.scheduler.models import ScheduleConfig


def schedule(circuit: QuantumCircuit,
             backend: BaseBackend,
             methods=None) -> Schedule:
    """
    Schedule a circuit to a pulse Schedule, using the backend, according to any specified methods.

    Args:
        circuit: The quantum circuit to translate
        backend: A backend instance, which contains hardware specific data required for scheduling
        methods: TODO
    Returns:
        Schedule corresponding to the input circuit
    """
    defaults = backend.defaults()
    schedule_config = ScheduleConfig(
        cmd_def=CmdDef.from_defaults(defaults.cmd_def, defaults.pulse_library),
        meas_map=backend.configuration().meas_map)
    return schedule_circuit(circuit, schedule_config, methods)
