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
from qiskit.scheduler import schedule

from qiskit.test.mock import FakeOpenPulse2Q
from qiskit.test import QiskitTestCase


class TestBasicSchedule(QiskitTestCase):
    """Scheduling tests."""

    def setUp(self):
        self.backend = FakeOpenPulse2Q()

    def test_minimize_earliness_pass(self):
        """Test forward (late) scheduling."""
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
        sched = schedule(qc, self.backend, methods="greedy")
        # X pulse on q0 should end at the start of the CNOT
        q0_x_time = sched.instructions[0][0]
        self.assertTrue(q0_x_time != 0)
        # TODO

    def test_greedy_pass(self):
        """Test backward (early) scheduling."""
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
        # X pulse on q0 should start at t=0
        q0_x_time = sched.instructions[0][0]
        self.assertTrue(q0_x_time == 0)
        # TODO

    def test_cmd_def_schedules_unaltered(self):
        """Test that forward scheduling doesn't change relative timing with a command."""
        pass
