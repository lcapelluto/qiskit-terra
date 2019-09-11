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

# pylint: disable=missing-docstring

"""Test the PulseDefaults part of the backend."""
import warnings

import numpy as np

from qiskit.test import QiskitTestCase
from qiskit.test.mock import FakeOpenPulse2Q
from qiskit.qobj.converters import QobjToInstructionConverter
from qiskit.qobj import PulseQobjInstruction
from qiskit.pulse import SamplePulse, Schedule, PulseError
from qiskit.pulse.channels import DriveChannel
from qiskit.pulse.schedule import ParameterizedSchedule


class TestPulseDefaults(QiskitTestCase):
    """Test the PulseDefaults creation and method usage."""

    def setUp(self):
        self.defs = FakeOpenPulse2Q().defaults()

    def test_buffer(self):
        """Test getting the buffer value."""
        self.assertEqual(self.defs.buffer, 10)

    def test_freq_est(self):
        """Test extracting qubit frequencies."""
        warnings.simplefilter("ignore")
        self.assertEqual(self.defs.qubit_freq_est[1],
                         5.0 * 1e9)
        self.assertEqual(self.defs.meas_freq_est[0],
                         6.5 * 1e9)
        warnings.simplefilter("default")

    def test_ops(self):
        """Test `ops`."""
        self.assertEqual(self.defs.ops(), ['u1', 'u3', 'cx', 'measure'])

    def test_has(self):
        """Test `has` and `assert_has`."""
        self.assertTrue(self.defs.has('u1', [0]))
        self.assertTrue(self.defs.has('cx', (0, 1)))
        self.assertTrue(self.defs.has('u3', 0))
        self.assertTrue(self.defs.has('measure', [0, 1]))
        self.assertFalse(self.defs.has('u1', [0, 1]))
        with self.assertRaises(PulseError):
            self.defs.assert_has('dne', [0])

    def test_op_qubits(self):
        """Test `op_qubits`."""
        self.assertEqual(self.defs.op_qubits('u1'), [0])
        self.assertEqual(self.defs.op_qubits('u3'), [0, 1])
        self.assertEqual(self.defs.op_qubits('cx'), [(0, 1)])
        self.assertEqual(self.defs.op_qubits('measure'), [(0, 1)])

    def test_qubit_ops(self):
        """Test `qubit_ops`."""
        self.assertEqual(self.defs.qubit_ops(0), ['u1', 'u3'])
        self.assertEqual(self.defs.qubit_ops(1), ['u3'])
        self.assertEqual(self.defs.qubit_ops((0, 1)), ['cx', 'measure'])

    def test_add(self):
        """Test add, and that errors are raised when expected."""
        sched = Schedule()
        sched.append(SamplePulse(np.ones(5))(DriveChannel(0)))
        defs = FakeOpenPulse2Q().defaults()
        defs.add('tmp', 1, sched)
        defs.add('tmp', 0, sched)
        self.assertIn('tmp', defs.ops())
        self.assertEqual(defs.op_qubits('tmp'), [0, 1])
        with self.assertRaises(PulseError):
            defs.add('tmp', (), sched)
        with self.assertRaises(PulseError):
            defs.add('tmp', 1, "not a schedule")

    def test_get(self):
        """Test `get`."""
        sched = Schedule()
        sched.append(SamplePulse(np.ones(5))(DriveChannel(0)))
        defs = FakeOpenPulse2Q().defaults()
        defs.add('tmp', 0, sched)
        self.assertEqual(sched.instructions, defs.get('tmp', (0,)).instructions)

    def test_remove(self):
        """Test removing a defined operation and removing an undefined operation."""
        sched = Schedule()
        sched.append(SamplePulse(np.ones(5))(DriveChannel(0)))
        self.defs.add('tmp', 0, sched)
        self.defs.remove('tmp', 0)
        self.assertFalse(self.defs.has('tmp', 0))
        with self.assertRaises(PulseError):
            self.defs.remove('not_there', (0,))

    def test_pop(self):
        """Test pop with default."""
        sched = Schedule()
        sched = sched.append(SamplePulse(np.ones(5))(DriveChannel(0)))
        self.defs.add('tmp', 0, sched)
        self.assertEqual(self.defs.pop('tmp', 0), sched)
        self.assertFalse(self.defs.has('tmp', 0))
        with self.assertRaises(PulseError):
            self.defs.pop('not_there', (0,))

    def test_parameterized_schedule(self):
        """Test adding parameterized schedule."""
        converter = QobjToInstructionConverter([], buffer=0)
        qobj = PulseQobjInstruction(name='pv', ch='u1', t0=10, val='P2*cos(np.pi*P1)')
        converted_instruction = converter(qobj)

        self.defs.add('pv_test', 0, converted_instruction)
        self.assertEqual(self.defs.get_parameters('pv_test', 0), ('P1', 'P2'))

        sched = self.defs.get('pv_test', 0, P1=0, P2=-1)
        self.assertEqual(sched.instructions[0][-1].command.value, -1)
        with self.assertRaises(PulseError):
            self.defs.get('pv_test', 0, 0, P1=-1)
        with self.assertRaises(PulseError):
            self.defs.get('pv_test', 0, P1=1, P2=2, P3=3)

    def test_sequenced_parameterized_schedule(self):
        """Test parametrized schedule consists of multiple instruction. """
        converter = QobjToInstructionConverter([], buffer=0)
        qobjs = [PulseQobjInstruction(name='fc', ch='d0', t0=10, phase='P1'),
                 PulseQobjInstruction(name='fc', ch='d0', t0=20, phase='P2'),
                 PulseQobjInstruction(name='fc', ch='d0', t0=30, phase='P3')]
        converted_instruction = [converter(qobj) for qobj in qobjs]

        self.defs.add('inst_seq', 0, ParameterizedSchedule(*converted_instruction,
                                                           name='inst_seq'))

        with self.assertRaises(PulseError):
            self.defs.get('inst_seq', 0, P1=1, P2=2, P3=3, P4=4, P5=5)

        with self.assertRaises(PulseError):
            self.defs.get('inst_seq', 0, P1=1)

        with self.assertRaises(PulseError):
            self.defs.get('inst_seq', 0, 1, 2, 3, P1=1)

        sched = self.defs.get('inst_seq', 0, 1, 2, 3)
        self.assertEqual(sched.instructions[0][-1].command.phase, 1)
        self.assertEqual(sched.instructions[1][-1].command.phase, 2)
        self.assertEqual(sched.instructions[2][-1].command.phase, 3)

        sched = self.defs.get('inst_seq', 0, P1=1, P2=2, P3=3)
        self.assertEqual(sched.instructions[0][-1].command.phase, 1)
        self.assertEqual(sched.instructions[1][-1].command.phase, 2)
        self.assertEqual(sched.instructions[2][-1].command.phase, 3)

        sched = self.defs.get('inst_seq', 0, 1, 2, P3=3)
        self.assertEqual(sched.instructions[0][-1].command.phase, 1)
        self.assertEqual(sched.instructions[1][-1].command.phase, 2)
        self.assertEqual(sched.instructions[2][-1].command.phase, 3)

    def test_default_building(self):
        """Test building of ops definition is properly built from backend."""
        self.assertTrue(self.defs.has('u1', (0,)))
        self.assertTrue(self.defs.has('u3', (0,)))
        self.assertTrue(self.defs.has('u3', 1))
        self.assertTrue(self.defs.has('cx', (0, 1)))
        self.assertEqual(self.defs.get_parameters('u1', 0), ('P1',))
        u1_minus_pi = self.defs.get('u1', 0, P1=1)
        fc_cmd = u1_minus_pi.instructions[0][-1].command
        self.assertEqual(fc_cmd.phase, -np.pi)
        for chan in u1_minus_pi.channels:
            self.assertEqual(chan.buffer, self.defs.buffer)

    def test_replace_pulse(self):
        """Test that the resulting op definitions are updated when a pulse is replaced by name."""
        original_sched = self.defs.get('u3', 0)
        no_change_sched = self.defs.get('u3', 1)

        new_samples = [0.1j, 0.1j]
        self.defs.replace_pulse('test_pulse_1', new_samples)
        self.assertEqual(self.defs.get('u3', 1), no_change_sched)

        new_sched = self.defs.get('u3', 0)
        new_pulse_samples = new_sched.instructions[0][1].command.samples
        self.assertTrue(np.allclose(new_pulse_samples, new_samples))
        self.assertFalse(np.allclose(
            original_sched.instructions[0][1].command.samples,
            new_pulse_samples))

    def test_repr(self):
        """Test that __repr__ method works."""
        self.assertEqual(
            repr(self.defs),
            "<PulseDefaults(1Q operations:\n  q0: ['u1', 'u3']\n  q1: ['u3']\nMulti qubit "
            "operations:\n  (0, 1): ['cx', 'measure']\nQubit Frequencies [GHz]\n[4.9, 5.0]"
            "\nMeasurement Frequencies [GHz]\n[6.5, 6.6] )>")
