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

from collections import defaultdict
from copy import deepcopy
from typing import List, Dict, Optional

from qiskit import QiskitError
from qiskit.circuit.measure import Measure
from qiskit.circuit.quantumcircuit import QuantumCircuit
from qiskit.extensions.standard.barrier import Barrier
from qiskit.providers.basebackend import BaseBackend
from qiskit import pulse
from qiskit.pulse.cmd_def import CmdDef
from qiskit.pulse.schedule import Schedule


def schedule(circuit: QuantumCircuit,
             backend: Optional[BaseBackend] = None,
             cmd_def: Optional[CmdDef] = None,
             meas_map: Optional[List[List[int]]] = None,
             greedy: bool = False) -> Schedule:
    """
    Basic scheduling pass from a circuit to a pulse Schedule, using the backend. By default, pulses
    are scheduled to occur as late as possible. This improves the outcome fidelity, because we may
    maximize the time that the qubit remains in a known state. To schedule pulses as early as
    possible, greedy can be set to True.

    Args:
        circuit: The quantum circuit to translate
        backend: A backend instance, which contains hardware specific data required for scheduling
        cmd_def: Command definition list
        meas_map: Groups of qubits that get measured together
        greedy: If True, schedule greedily, else schedule pulses as late as possible
    Returns:
        Schedule corresponding to the input circuit
    """
    if cmd_def == None:
        if backend == None:
            raise QiskitError("Must supply either a backend or CmdDef for scheduling passes.")
        defaults = backend.defaults()
        cmd_def = CmdDef.from_defaults(defaults.cmd_def, defaults.pulse_library)
    if meas_map == None:
        if backend == None:
            raise QiskitError("Must supply either a backend or a meas_map for scheduling passes.")
        meas_map = format_meas_map(backend.configuration().meas_map)

    if greedy:
        return greedy_schedule(circuit, cmd_def, meas_map)
    return minimize_earliness_schedule(circuit, cmd_def, meas_map)


def minimize_earliness_schedule(circuit: QuantumCircuit,
                                cmd_def: CmdDef,
                                meas_map: List[List[int]]) -> Schedule:
    """
    Return the input circuit's equivalent pulse Schedule by performing the most basic scheduling
    pass on it. The pulses are scheduled as late as possible.

    Args:
        circuit: The quantum circuit to translate
        cmd_def: Command definition list
        meas_map: Groups of qubits that get measured together
    Returns:
        Late scheduled pulse Schedule
    """
    sched = Schedule(name=circuit.name)

    qubit_available_until = defaultdict(lambda:float("inf"))
    measured_qubits = set()

    def update_times(inst_qubits: List[int], shift: int = 0) -> None:
        """Update the time tracker for all inst_qubits to the given time."""
        for q in qubit_available_until.keys():
            if q in inst_qubits:
                qubit_available_until[q] = 0
            else:
                qubit_available_until[q] += shift

    def insert_measures_front():
        """Based off the Set measured_qubits, add measures to the schedule."""
        nonlocal sched
        measures = set()
        for q in measured_qubits:
            measures.add(tuple(meas_map[q]))
        for qubits in measures:
            cmd = cmd_def.get('measure', qubits)
            cmd_start_time = min([qubit_available_until[q] for q in qubits]) - cmd.duration
            if cmd_start_time == float("inf"):
                cmd_start_time = 0
            shift_amount = max(0, -cmd_start_time)
            cmd_start_time = max(cmd_start_time, 0)
            sched = pulse.ops.union((shift_amount, sched), (cmd_start_time, cmd))
            update_times(qubits, shift_amount)
        measured_qubits.clear()

    for i in reversed(range(len(circuit.data))):
        inst, qregs, _ = circuit.data[i]
        inst_qubits = [chan.index for chan in qregs]
        if isinstance(inst, Barrier):
            update_times(inst_qubits)
            continue
        if any(q in measured_qubits for q in inst_qubits):
            insert_measures_front()
        if isinstance(inst, Measure):
            measured_qubits.update(inst_qubits)
        else:
            cmd = cmd_def.get(inst.name, inst_qubits, *inst.params)
            cmd_start_time = min([qubit_available_until[q] for q in inst_qubits]) - cmd.duration
            if cmd_start_time == float("inf"):
                cmd_start_time = 0
            shift_amount = max(0, -cmd_start_time)
            cmd_start_time = max(cmd_start_time, 0)
            sched = pulse.ops.union((shift_amount, sched), (cmd_start_time, cmd))
            update_times(inst_qubits, shift_amount)
    insert_measures_front()

    return sched


def greedy_schedule(circuit: QuantumCircuit,
                    cmd_def: CmdDef,
                    meas_map: List[List[int]]) -> Schedule:
    """
    Return the input circuit's equivalent pulse Schedule by performing the most basic scheduling
    pass on it. The pulses are greedily scheduled, meaning that pulses are played as early as
    possible.

    Args:
        circuit: The quantum circuit to translate
        cmd_def: Command definition list
        meas_map: Groups of qubits that get measured together
    Returns:
        Greedily scheduled pulse Schedule
    """
    sched = Schedule(name=circuit.name)

    qubit_time_available = defaultdict(int)
    measured_qubits = set()

    def update_times(qubits: List[int], time: int) -> None:
        """Update the time tracker for all qubits to the given time."""
        for q in qubits:
            qubit_time_available[q] = time

    def add_measures():
        """Based off the Set measured_qubits, add measures to the schedule."""
        nonlocal sched
        measures = set()
        for q in measured_qubits:
            measures.add(tuple(meas_map[q]))
        for qubits in measures:
            time = max(qubit_time_available[q] for q in qubits)
            cmd = cmd_def.get('measure', qubits)
            sched |= cmd << time
            update_times(qubits, time + cmd.duration)
        measured_qubits.clear()

    for inst, qregs, _ in circuit:
        qubits = [chan.index for chan in qregs]
        if isinstance(inst, Barrier):
            update_times(qubits, max(qubit_time_available[q] for q in qubits))
            continue
        if any(q in measured_qubits for q in qubits):
            add_measures()
        if isinstance(inst, Measure):
            measured_qubits.update(qubits)
        else:
            cmd = cmd_def.get(inst.name, qubits, *inst.params)
            time = max(qubit_time_available[q] for q in qubits)
            sched |= cmd << time
            update_times(qubits, time + cmd.duration)
    add_measures()

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
