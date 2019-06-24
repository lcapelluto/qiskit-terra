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
from qiskit.pulse.channels import AcquireChannel
from qiskit.pulse.commands import AcquireInstruction
from qiskit.scheduler import schedule

from qiskit.test.mock import FakeOpenPulse2Q
from qiskit.test import QiskitTestCase


class TestBasicSchedule(QiskitTestCase):
    """Scheduling tests."""

    def setUp(self):
        self.backend = FakeOpenPulse2Q()

    def test_alap_pass(self):
        """Test ALAP scheduling."""
        q = QuantumRegister(2)
        c = ClassicalRegister(2)
        qc = QuantumCircuit(q, c)
        qc.x(q[0])
        qc.x(q[1])
        qc.barrier(q[1])
        qc.x(q[1])
        qc.barrier(q[0], q[1])
        qc.cx(q[0], q[1])
        qc.measure(q, c)
        sched = schedule(qc, self.backend)
        # X pulse on q0 should end at the start of the CNOT
        insts = sched.instructions
        self.assertNotEqual(insts[-1][0], 0)
        self.assertEqual(insts[-1][0], 28)
        self.assertEqual(insts[-2][0], 0)
        self.assertEqual(insts[-3][0], 28)
        self.assertEqual(insts[0][0], 78)
        self.assertEqual(insts[1][0], 78)
        self.assertEqual(insts[2][0], 78)

    def test_asap_pass(self):
        """Test ASAP scheduling."""
        q = QuantumRegister(2)
        c = ClassicalRegister(2)
        qc = QuantumCircuit(q, c)
        qc.x(q[0])
        qc.x(q[1])
        qc.barrier(q[1])
        qc.x(q[1])
        qc.barrier(q[0], q[1])
        qc.cx(q[0], q[1])
        qc.measure(q, c)
        sched = schedule(qc, self.backend, method="as_soon_as_possible")
        insts = sched.instructions
        # X pulse on q0 should start at t=0
        self.assertEqual(insts[0][0], 0)
        self.assertEqual(insts[1][0], 0)
        self.assertEqual(insts[2][0], 28)
        self.assertEqual(insts[3][0], 56)
        self.assertEqual(insts[4][0], 66)
        self.assertEqual(insts[5][0], 76)
        self.assertEqual(insts[6][0], 76)
        self.assertEqual(insts[7][0], 78)

    def test_alap_resource_respecting(self):
        """Test that the ALAP pass properly respects busy resources when backwards scheduling.
        For instance, a CX on 0 and 1 followed by an X on only 1 must respect both qubits'
        timeline."""
        q = QuantumRegister(2)
        c = ClassicalRegister(2)
        qc = QuantumCircuit(q, c)
        qc.cx(q[0], q[1])
        qc.x(q[1])
        sched = schedule(qc, self.backend, method="as_late_as_possible")
        insts = sched.instructions
        self.assertEqual(insts[-4][0], 0)
        self.assertEqual(insts[-5][0], 22)

        qc = QuantumCircuit(q, c)
        qc.cx(q[0], q[1])
        qc.x(q[1])
        qc.measure(q, c)
        sched = schedule(qc, self.backend, method="as_late_as_possible")
        self.assertEqual(sched.instructions[0][0], 50)

    def test_cmd_def_schedules_unaltered(self):
        """Test that forward scheduling doesn't change relative timing with a command."""
        q = QuantumRegister(2)
        c = ClassicalRegister(2)
        qc = QuantumCircuit(q, c)
        qc.cx(q[0], q[1])
        sched1 = schedule(qc, self.backend, method="as_soon_as_possible")
        sched2 = schedule(qc, self.backend, method="as_late_as_possible")
        self.assertNotEqual(sched1.instructions, sched2.instructions)
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
        qc.x(q[0])
        qc.cx(q[0], q[1])
        qc.measure(q[0], c[0])
        qc.measure(q[1], c[1])
        qc.measure(q[1], c[1])
        sched = schedule(qc, self.backend, method="as_soon_as_possible")
        insts = sched.instructions
        self.assertEqual(insts[5][0], 50)
        self.assertTrue(AcquireChannel(0) in insts[7][1].channels)
        self.assertTrue(AcquireChannel(1) in insts[7][1].channels)
        self.assertEqual(insts[8][0], 60)
        self.assertIsInstance(insts[7][1], AcquireInstruction)
        self.assertIsInstance(insts[10][1], AcquireInstruction)
