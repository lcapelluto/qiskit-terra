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

"""Test cases for the pulse scheduler passes."""

from qiskit import QuantumRegister, ClassicalRegister, QuantumCircuit
from qiskit.pulse.schedule import Schedule
from qiskit.scheduler import schedule

from qiskit.test.mock import FakeOpenPulse2Q
from qiskit.test import QiskitTestCase

from qiskit.pulse.cmd_def import CmdDef


class TestBasicSchedule(QiskitTestCase):
    """Scheduling tests."""

    def setUp(self):
        self.backend = FakeOpenPulse2Q()
        defaults = self.backend.defaults()
        self.cmd_def = CmdDef.from_defaults(defaults.cmd_def, defaults.pulse_library)

    def test_alap_pass(self):
        """Test ALAP scheduling."""
        q = QuantumRegister(2)
        c = ClassicalRegister(2)
        qc = QuantumCircuit(q, c)
        qc.u2(3.14, 1.57, q[0])
        qc.u2(0.5, 0.25, q[1])
        qc.barrier(q[1])
        qc.u2(0.5, 0.25, q[1])
        qc.barrier(q[0], q[1])
        qc.cx(q[0], q[1])
        qc.measure(q, c)
        sched = schedule(qc, self.backend)
        # X pulse on q0 should end at the start of the CNOT
        expected = Schedule(
            (28, self.cmd_def.get('u2', [0], 3.14, 1.57)),
            self.cmd_def.get('u2', [1], 0.5, 0.25),
            (28, self.cmd_def.get('u2', [1], 0.5, 0.25)),
            (56, self.cmd_def.get('cx', [0, 1])),
            (78, self.cmd_def.get('measure', [0, 1])))
        for actual, expected in zip(sched.instructions, expected.instructions):
            self.assertEqual(actual[0], expected[0])
            self.assertEqual(actual[1].command, expected[1].command)
            self.assertEqual(actual[1].channels, expected[1].channels)

    def test_asap_pass(self):
        """Test ASAP scheduling."""
        q = QuantumRegister(2)
        c = ClassicalRegister(2)
        qc = QuantumCircuit(q, c)
        qc.u2(3.14, 1.57, q[0])
        qc.u2(0.5, 0.25, q[1])
        qc.barrier(q[1])
        qc.u2(0.5, 0.25, q[1])
        qc.barrier(q[0], q[1])
        qc.cx(q[0], q[1])
        qc.measure(q, c)
        sched = schedule(qc, self.backend, method="as_soon_as_possible")
        # X pulse on q0 should start at t=0
        expected = Schedule(
            self.cmd_def.get('u2', [0], 3.14, 1.57),
            self.cmd_def.get('u2', [1], 0.5, 0.25),
            (28, self.cmd_def.get('u2', [1], 0.5, 0.25)),
            (56, self.cmd_def.get('cx', [0, 1])),
            (78, self.cmd_def.get('measure', [0, 1])))
        for actual, expected in zip(sched.instructions, expected.instructions):
            self.assertEqual(actual[0], expected[0])
            self.assertEqual(actual[1].command, expected[1].command)
            self.assertEqual(actual[1].channels, expected[1].channels)

    def test_alap_resource_respecting(self):
        """Test that the ALAP pass properly respects busy resources when backwards scheduling.
        For instance, a CX on 0 and 1 followed by an X on only 1 must respect both qubits'
        timeline."""
        q = QuantumRegister(2)
        c = ClassicalRegister(2)
        qc = QuantumCircuit(q, c)
        qc.cx(q[0], q[1])
        qc.u2(0.5, 0.25, q[1])
        sched = schedule(qc, self.backend, method="as_late_as_possible")
        insts = sched.instructions
        self.assertEqual(insts[0][0], 0)
        self.assertEqual(insts[4][0], 22)

        qc = QuantumCircuit(q, c)
        qc.cx(q[0], q[1])
        qc.u2(0.5, 0.25, q[1])
        qc.measure(q, c)
        sched = schedule(qc, self.backend, method="as_late_as_possible")
        self.assertEqual(sched.instructions[-1][0], 50)

    def test_cmd_def_schedules_unaltered(self):
        """Test that forward scheduling doesn't change relative timing with a command."""
        q = QuantumRegister(2)
        c = ClassicalRegister(2)
        qc = QuantumCircuit(q, c)
        qc.cx(q[0], q[1])
        sched1 = schedule(qc, self.backend, method="as_soon_as_possible")
        sched2 = schedule(qc, self.backend, method="as_late_as_possible")
        self.assertEqual(sched1.instructions, sched2.instructions)
        insts = sched1.instructions
        self.assertEqual(insts[0][0], 0)
        self.assertEqual(insts[1][0], 10)
        self.assertEqual(insts[2][0], 20)
        self.assertEqual(insts[3][0], 20)

    def test_measure_combined(self):
        """Test that measures on different qubits are combined, but measures on the same qubit
        adds another measure to the schedule."""
        q = QuantumRegister(2)
        c = ClassicalRegister(2)
        qc = QuantumCircuit(q, c)
        qc.u2(3.14, 1.57, q[0])
        qc.cx(q[0], q[1])
        qc.measure(q[0], c[0])
        qc.measure(q[1], c[1])
        qc.measure(q[1], c[1])
        sched = schedule(qc, self.backend, method="as_soon_as_possible")
        expected = Schedule(
            self.cmd_def.get('u2', [0], 3.14, 1.57),
            (28, self.cmd_def.get('cx', [0, 1])),
            (50, self.cmd_def.get('measure', [0, 1])),
            (60, self.cmd_def.get('measure', [0, 1])))
        for actual, expected in zip(sched.instructions, expected.instructions):
            self.assertEqual(actual[0], expected[0])
            self.assertEqual(actual[1].command, expected[1].command)
            self.assertEqual(actual[1].channels, expected[1].channels)

    def test_extra_barriers(self):
        """Test that schedules are built properly with extra barriers."""
        q = QuantumRegister(2)
        c = ClassicalRegister(2)
        qc = QuantumCircuit(q, c)
        qc.barrier(q[0])
        qc.barrier(q[1])
        qc.cx(q[0], q[1])
        qc.u2(3, 1, q[0])
        sched = schedule(qc, self.backend, method="asap")
        expected = Schedule(
            self.cmd_def.get('cx', [0, 1]),
            (22, self.cmd_def.get('u2', [0], 3, 1)))
        for actual, expected in zip(sched.instructions, expected.instructions):
            self.assertEqual(actual[0], expected[0])
            self.assertEqual(actual[1].command, expected[1].command)
            self.assertEqual(actual[1].channels, expected[1].channels)

    def test_schedule_multi(self):
        """Test scheduling multiple circuits at once."""
        q = QuantumRegister(2)
        c = ClassicalRegister(2)
        qc0 = QuantumCircuit(q, c)
        qc0.cx(q[0], q[1])
        qc1 = QuantumCircuit(q, c)
        qc1.cx(q[0], q[1])
        schedules = schedule([qc0, qc1], self.backend)
        expected_insts = schedule(qc0, self.backend).instructions
        for actual, expected in zip(schedules[0].instructions, expected_insts):
            self.assertEqual(actual[0], expected[0])
            self.assertEqual(actual[1].command, expected[1].command)
            self.assertEqual(actual[1].channels, expected[1].channels)
