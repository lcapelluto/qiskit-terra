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

"""The most straightforward scheduling methods: scheduling as early or as late as possible."""

from collections import defaultdict
from typing import List

from qiskit.circuit.measure import Measure
from qiskit.circuit.quantumcircuit import QuantumCircuit
from qiskit.extensions.standard.barrier import Barrier
from qiskit import QiskitError
from qiskit.pulse.exceptions import PulseError
from qiskit.pulse.schedule import Schedule

from qiskit.scheduler.models import ScheduleConfig, CircuitPulseDef


def as_soon_as_possible(circuit: QuantumCircuit,
                        schedule_config: ScheduleConfig) -> Schedule:
    """
    Return a pulse Schedule which nails down the timing between circuit element schedules by
    scheduling pulses as soon as possible, where resources are binned by qubit. The timing
    between instructions within each circuit schedule are respected.

    Args:
        circuit: The quantum circuit to translate
        schedule_config: Backend specific parameters used for building the Schedule
    Returns:
        A final schedule, pulses occuring as early as possible
    """
    circ_pulse_defs = translate_gates_to_pulse_defs(circuit, schedule_config)

    def update_times(inst_qubits: List[int], time: int = 0) -> None:
        """Update the time tracker for all inst_qubits to the given time."""
        for q in inst_qubits:
            qubit_time_available[q] = time

    sched = Schedule()
    qubit_time_available = defaultdict(int)

    for circ_pulse_def in circ_pulse_defs:
        time = max(qubit_time_available[q] for q in circ_pulse_def.qubits)
        if isinstance(circ_pulse_def.schedule, Barrier):
            update_times(circ_pulse_def.qubits, time)
        else:
            sched |= circ_pulse_def.schedule << time
            update_times(circ_pulse_def.qubits, time + circ_pulse_def.schedule.duration)
    return sched


def as_late_as_possible(circuit: QuantumCircuit,
                        schedule_config: ScheduleConfig) -> Schedule:
    """
    Return a pulse Schedule which nails down the timing between circuit element schedules by
    scheduling pulses as late as possible on a resource, where resources are binned by qubit. The
    timing between instructions within each circuit schedule are respected.

    This method should improves the outcome fidelity over ASAP scheduling, because we may
    maximize the time that the qubit remains in the ground state.

    Args:
        circuit: The quantum circuit to translate
        schedule_config: Backend specific parameters used for building the Schedule
    Returns:
        A final schedule, pulses occuring as late as possible
    """
    circ_pulse_defs = translate_gates_to_pulse_defs(circuit, schedule_config)

    def update_times(inst_qubits: List[int], shift: int = 0) -> None:
        """Update the time tracker for all inst_qubits to the given time."""
        for q in qubit_available_until.keys():
            if q in inst_qubits:
                qubit_available_until[q] = 0
            else:
                qubit_available_until[q] += shift

    sched = Schedule()
    qubit_available_until = defaultdict(lambda: float("inf"))

    for circ_pulse_def in reversed(circ_pulse_defs):
        if isinstance(circ_pulse_def.schedule, Barrier):
            update_times(circ_pulse_def.qubits)
        else:
            cmd_sched = circ_pulse_def.schedule
            cmd_start_time = (min([qubit_available_until[q] for q in circ_pulse_def.qubits])
                              - cmd_sched.duration)
            if cmd_start_time == float("inf"):
                cmd_start_time = 0
            shift_amount = max(0, -cmd_start_time)
            cmd_start_time = max(cmd_start_time, 0)
            sched = sched.shift(shift_amount) | cmd_sched.shift(cmd_start_time)
            update_times(circ_pulse_def.qubits, shift_amount)
    return sched


def translate_gates_to_pulse_defs(circuit: QuantumCircuit,
                                  schedule_config: ScheduleConfig) -> List[CircuitPulseDef]:
    """
    Without concern for the final schedule, extract and return a list of Schedules and the qubits
    they operate on, for each element encountered in the input circuit. Measures are grouped when
    possible, so qc.measure(q0, c0)/qc.measure(q1, c1) will generate a synchronous measurement
    pulse.

    Args:
        circuit: The quantum circuit to translate
        schedule_config: Backend specific parameters used for building the Schedule
    Returns:
        A list of CircuitPulseDefs: the pulse definition for each circuit element
    Raises:
        QiskitError: If circuit uses a command that isn't defined in config.cmd_def
    """
    cmd_def = schedule_config.cmd_def
    meas_map = schedule_config.meas_map

    def get_measure_schedule() -> CircuitPulseDef:
        """Create a schedule to measure the qubits queued for measuring."""
        measures = set()
        all_qubits = set()
        sched = Schedule()
        for q in measured_qubits:
            measures.add(tuple(meas_map[q]))
        for qubits in measures:
            all_qubits.update(qubits)
            sched |= cmd_def.get('measure', qubits)
        measured_qubits.clear()
        return CircuitPulseDef(schedule=sched, qubits=all_qubits)

    circ_pulse_defs = []
    measured_qubits = set()
    for inst, qubits, _ in circuit.data:
        inst_qubits = [chan.index for chan in qubits]
        if any(q in measured_qubits for q in inst_qubits):
            circ_pulse_defs.append(get_measure_schedule())
        if isinstance(inst, Barrier):
            circ_pulse_defs.append(CircuitPulseDef(schedule=inst, qubits=inst_qubits))
        elif isinstance(inst, Measure):
            measured_qubits.update(inst_qubits)
        else:
            try:
                circ_pulse_defs.append(
                    CircuitPulseDef(schedule=cmd_def.get(inst.name, inst_qubits, *inst.params),
                                    qubits=inst_qubits))
            except PulseError:
                raise QiskitError("Operation '{0}' on qubit(s) {1} not supported by the backend "
                                  "command definition. Did you remember to transpile your input "
                                  "circuit for the same backend?".format(inst.name, inst_qubits))
    if measured_qubits:
        circ_pulse_defs.append(get_measure_schedule())

    return circ_pulse_defs
