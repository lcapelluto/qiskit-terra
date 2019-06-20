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

from collections import defaultdict, namedtuple
from typing import List, Dict, Optional

from qiskit import QiskitError
from qiskit.circuit.measure import Measure
from qiskit.circuit.quantumcircuit import QuantumCircuit
from qiskit.extensions.standard.barrier import Barrier
from qiskit.providers.basebackend import BaseBackend
from qiskit import pulse
from qiskit.pulse.cmd_def import CmdDef
from qiskit.pulse.schedule import Schedule


CircuitPulseDef = namedtuple('CircuitPulseDef', ['schedule', 'qubits'])


def schedule(circuit: QuantumCircuit,
             backend: Optional[BaseBackend] = None,
             cmd_def: Optional[CmdDef] = None,
             meas_map: Optional[List[List[int]]] = None,
             greedy: bool = False) -> Schedule:
    """
    Basic scheduling pass from a circuit to a pulse Schedule, using the backend. By default, pulses
    are scheduled to occur as late as possible. This improves the outcome fidelity, because we may
    maximize the time that the qubit remains in the ground state. To schedule pulses as early as
    possible, greedy can be set to True.

    Args:
        circuit: The quantum circuit to translate
        backend: A backend instance, which contains hardware specific data required for scheduling
        cmd_def: Command definition list
        meas_map: List of groups of qubits that get measured together
        greedy: If True, schedule greedily, else schedule pulses as late as possible
    Returns:
        Schedule corresponding to the input circuit
    Raises:
        QiskitError: if backend or cmd_def and meas_map are not provided.
    """
    if cmd_def is None:
        if backend is None:
            raise QiskitError("Must supply either a backend or CmdDef for scheduling passes.")
        defaults = backend.defaults()
        cmd_def = CmdDef.from_defaults(defaults.cmd_def, defaults.pulse_library)
    if meas_map is None:
        if backend is None:
            raise QiskitError("Must supply either a backend or a meas_map for scheduling passes.")
        meas_map = format_meas_map(backend.configuration().meas_map)

    circ_pulse_defs = translate_gates_to_pulse_defs(circuit, cmd_def, meas_map)
    if greedy:
        return greedy_schedule(circ_pulse_defs)
    return minimize_earliness_schedule(circ_pulse_defs)


def translate_gates_to_pulse_defs(circuit: QuantumCircuit,
                                  cmd_def: CmdDef,
                                  meas_map: Dict[int, List[int]]) -> List[CircuitPulseDef]:
    """
    Without concern for the final schedule, extract and return a list of Schedules and the qubits
    they operate on, for each element encountered in the input circuit. Measures are grouped when
    possible, so qc.measure(q0, c0)/qc.measure(q1, c1) will generate a synchronous measurement
    pulse.

    Args:
        circuit: The quantum circuit to translate
        cmd_def: Command definition list
        meas_map: Mapping of groups of qubits that get measured together
    Returns:
        A list of CircuitPulseDefs: the pulse definition for each circuit element
    """
    def get_measure_schedule() -> Schedule:
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
    for inst, qregs, _ in circuit.data:
        inst_qubits = [chan.index for chan in qregs]
        if any(q in measured_qubits for q in inst_qubits):
            circ_pulse_defs.append(get_measure_schedule())
        if isinstance(inst, Barrier):
            circ_pulse_defs.append(CircuitPulseDef(schedule=inst, qubits=inst_qubits))
        elif isinstance(inst, Measure):
            measured_qubits.update(inst_qubits)
        else:
            circ_pulse_defs.append(
                CircuitPulseDef(schedule=cmd_def.get(inst.name, inst_qubits, *inst.params),
                                qubits=inst_qubits))
    if measured_qubits:
        circ_pulse_defs.append(get_measure_schedule())

    return circ_pulse_defs


def greedy_schedule(circ_pulse_defs: List[CircuitPulseDef]) -> Schedule:
    """
    Return a pulse Schedule which nails down the timing between circuit element schedules by
    scheduling greedily, where a resources are binned by qubit. The timing between instructions
    within each circuit schedule are respected.

    Args:
        circ_pulse_defs: the pulse definition for each circuit element
    Returns:
        A final schedule, greedily scheduled
    """
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


def minimize_earliness_schedule(circ_pulse_defs: List[CircuitPulseDef]) -> Schedule:
    """
    Return a pulse Schedule which nails down the timing between circuit element schedules by
    minimizing the earliness of pulses on a resource, where resources are binned by qubit. The
    timing between instructions within each circuit schedule are respected.

    Args:
        circ_pulse_defs: the pulse definition for each circuit element
    Returns:
        A final schedule, minimizing earliness
    """
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
            cmd_start_time = min([qubit_available_until[q] for q in circ_pulse_def.qubits]) \
                             - cmd_sched.duration
            if cmd_start_time == float("inf"):
                cmd_start_time = 0
            shift_amount = max(0, -cmd_start_time)
            cmd_start_time = max(cmd_start_time, 0)
            sched = pulse.ops.union((shift_amount, sched), (cmd_start_time, cmd_sched))
            update_times(circ_pulse_def.qubits, shift_amount)
    return sched


def format_meas_map(meas_map: List[List[int]]) -> Dict[int, List[int]]:
    """
    Return a mapping from qubit label to measurement group given the nested list meas_map returned
    by a backend configuration. (Qubits can not always be measured independently.)

    Args:
        meas_map: Groups of qubits that get measured together, for example: [[0, 1], [2, 3, 4]]
    Returns:
        Measure map in map format
    """
    qubit_mapping = {}
    for sublist in meas_map:
        sublist.sort()
        for q in sublist:
            qubit_mapping[q] = sublist
    return qubit_mapping
