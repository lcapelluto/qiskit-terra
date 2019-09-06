# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2017, 2019.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Model and schema for pulse defaults."""
from collections import defaultdict
from marshmallow.validate import Length, Range

from qiskit.util import _to_tuple
from qiskit.validation import BaseModel, BaseSchema, bind_schema
from qiskit.validation.base import ObjSchema
from qiskit.validation.fields import (Integer, List, Nested, Number, String)
from qiskit.qobj import PulseLibraryItemSchema, PulseQobjInstructionSchema
from qiskit.qobj.converters import QobjToInstructionConverter
from qiskit.pulse.schedule import Schedule, ParameterizedSchedule
from qiskit.pulse.exceptions import PulseError


class MeasurementKernelSchema(BaseSchema):
    """Schema for MeasurementKernel."""

    # Optional properties.
    name = String()
    params = Nested(ObjSchema)


class DiscriminatorSchema(BaseSchema):
    """Schema for Discriminator."""

    # Optional properties.
    name = String()
    params = Nested(ObjSchema)


class CommandSchema(BaseSchema):
    """Schema for Command."""

    # Required properties.
    name = String(required=True)

    # Optional properties.
    qubits = List(Integer(validate=Range(min=0)),
                  validate=Length(min=1))
    sequence = Nested(PulseQobjInstructionSchema, many=True)


class PulseDefaultsSchema(BaseSchema):
    """Schema for PulseDefaults."""

    # Required properties.
    qubit_freq_est = List(Number(), required=True, validate=Length(min=1))
    meas_freq_est = List(Number(), required=True, validate=Length(min=1))
    buffer = Integer(required=True, validate=Range(min=0))
    pulse_library = Nested(PulseLibraryItemSchema, required=True, many=True)
    cmd_def = Nested(CommandSchema, many=True, required=True)

    # Optional properties.
    meas_kernel = Nested(MeasurementKernelSchema)
    discriminator = Nested(DiscriminatorSchema)


@bind_schema(MeasurementKernelSchema)
class MeasurementKernel(BaseModel):
    """Model for MeasurementKernel.

    Please note that this class only describes the required fields. For the
    full description of the model, please check ``MeasurementKernelSchema``.
    """
    pass


@bind_schema(DiscriminatorSchema)
class Discriminator(BaseModel):
    """Model for Discriminator.

    Please note that this class only describes the required fields. For the
    full description of the model, please check ``DiscriminatorSchema``.
    """
    pass


@bind_schema(CommandSchema)
class Command(BaseModel):
    """Model for Command.

    Please note that this class only describes the required fields. For the
    full description of the model, please check ``CommandSchema``.

    Attributes:
        name (str): Pulse command name.
    """
    def __init__(self, name, **kwargs):
        self.name = name

        super().__init__(**kwargs)


@bind_schema(PulseDefaultsSchema)
class PulseDefaults(BaseModel):
    """Model for PulseDefaults.

    Please note that this class only describes the required fields. For the
    full description of the model, please check ``PulseDefaultsSchema``.

    Attributes:
        qubit_freq_est (list[number]): Estimated qubit frequencies in GHz.
        meas_freq_est (list[number]): Estimated measurement cavity frequencies
            in GHz.
        buffer (int): Default buffer time (in units of dt) between pulses.
        pulse_library (list[PulseLibraryItem]): Backend pulse library.
        cmd_def (list[Command]): Backend command definition.
    """

    def __init__(self, qubit_freq_est, meas_freq_est, buffer,
                 pulse_library, cmd_def, **kwargs):
        self._qubit_freq_est = qubit_freq_est
        self._meas_freq_est = meas_freq_est
        self.buffer = buffer
        self.pulse_library = pulse_library
        self.cmd_def = cmd_def
        self._ops_def = defaultdict(dict)
        self._qubit_ops = defaultdict(list)

        converter = QobjToInstructionConverter(pulse_library, buffer)
        for op in cmd_def:
            qubits = _to_tuple(op.qubits)
            self.add(
                op.name,
                qubits,
                ParameterizedSchedule(*[converter(inst) for inst in op.sequence], name=op.name))
            self._qubit_ops[qubits].append(op.name)

        super().__init__(**kwargs)

    def qubit_freq_est(self, qubit):
        """
        Return the estimated resonant frequency for the given qubit in Hz.

        Args:
            qubit: Index of the qubit of interest.
        Raises:
            PulseError: If the frequency is not available.
        """
        try:
            return self._qubit_freq_est[qubit] * 1e9
        except IndexError:
            raise PulseError("Cannot get the qubit frequency for qubit {qub}, this system only "
                             "has {num} qubits.".format(qub=qubit, num=self.n_qubits))

    def meas_freq_est(self, qubit):
        """
        Return the estimated measurement stimulus frequency to readout from the given qubit.

        Args:
            qubit: Index of the qubit of interest.
        Raises:
            PulseError: If the frequency is not available.
        """
        try:
            return self._meas_freq_est[qubit] * 1e9
        except IndexError:
            raise PulseError("Cannot get the measurement frequency for qubit {qub}, this system "
                             "only has {num} qubits.".format(qub=qubit, num=self.n_qubits))

    @property
    def ops(self):
        """
        Return all operations which are defined by default. (This is essentially the basis gates
        along with measure and reset.)
        """
        return list(self._ops_def.keys())

    def op_qubits(self, operation):
        """
        Return a list of the qubits for which the given operation is defined. Single qubit
        operations return a flat list, and multiqubit operations return a list of tuples.
        """
        return [qs[0] if len(qs) == 1 else qs
                for qs in sorted(self._ops_def[operation].keys())]

    def qubit_ops(self, qubits):
        """
        Return a list of the operation names that are defined by the backend for the given qubit
        or qubits.
        """
        return self._qubit_ops[_to_tuple(qubits)]

    def has(self, operation, qubits):
        """
        Is the operation defined for the given qubits?

        Args:
            operation: The operation for which to look.
            qubits: The specific qubits for the operation.
        """
        return operation in self._ops_def and \
            _to_tuple(qubits) in self._ops_def[operation]

    def get(self,
            operation,
            qubits,
            *params,
            **kwparams):
        """
        Return the defined Schedule for the given operation on the given qubits.

        Args:
            operation: Name of the operation.
            qubits: The qubits for the operation.
            *params: Command parameters for generating the output schedule.
            **kwparams: Keyworded command parameters for generating the schedule.

        Raises:
            PulseError: If the operation is not defined on the qubits.
        """
        qubits = _to_tuple(qubits)
        if not self.has(operation, qubits):
            raise PulseError("Operation {op} for qubits {qubits} is not defined for this "
                             "system.".format(op=operation, qubits=qubits))
        sched = self._ops_def[operation].get(qubits)
        if isinstance(sched, ParameterizedSchedule):
            sched = sched.bind_parameters(*params, **kwparams)
        return sched

    def get_parameters(self, operation, qubits):
        """
        Return the list of parameters taken by the given operation on the given qubits.

        Raises:
            PulseError: If the operation is not defined on the qubits.
        """
        qubits = _to_tuple(qubits)
        if not self.has(operation, qubits):
            raise PulseError("Operation {op} for qubits {qubits} is not defined for this "
                             "system.".format(op=operation, qubits=qubits))
        return self._ops_def[operation][qubits].parameters

    def add(self, operation, qubits, schedule):
        """
        Add a new known operation.

        Args:
            operation: The name of the operation to add.
            qubits: The qubits which the operation applies to.
            schedule: The Schedule that implements the given operation.
        Raises:
            PulseError: If the qubits are provided as an empty iterable.
        """
        qubits = _to_tuple(qubits)
        if qubits == ():
            raise PulseError("Cannot add definition {} with no target qubits.".format(operation))
        if not (isinstance(schedule, Schedule) or isinstance(schedule, ParameterizedSchedule)):
            raise PulseError("Attemping to add an invalid schedule type.")
        self._ops_def[operation][qubits] = schedule

    def remove(self, operation, qubits):
        """Remove the given operation from the defined operations.

        Args:
            operation: The name of the operation to add.
            qubits: The qubits which the operation applies to.
        """
        qubits = _to_tuple(qubits)
        if not self.has(operation, qubits):
            raise PulseError("Operation {op} for qubits {qubits} is not defined for this "
                             "system.".format(op=operation, qubits=qubits))
        self._ops_def[operation].pop(qubits)

    def draw(self) -> None:
        """
        Visualize the topology of the device, showing qubits, their interconnections, and the
        channels which interact with them. Optionally print a listing of the supported 1Q and
        2Q gates.
        """
        # TODO: Implement the draw method.
        raise NotImplementedError
