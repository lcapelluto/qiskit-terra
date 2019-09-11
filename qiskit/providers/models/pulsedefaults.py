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
import warnings

from collections import defaultdict
from marshmallow.validate import Length, Range

from qiskit.util import _to_tuple
from qiskit.validation import BaseModel, BaseSchema, bind_schema
from qiskit.validation.base import ObjSchema
from qiskit.validation.fields import (Integer, List, Nested, Number, String)
from qiskit.qobj import PulseLibraryItemSchema, PulseQobjInstructionSchema, PulseLibraryItem
from qiskit.qobj.converters import QobjToInstructionConverter
from qiskit.pulse import CmdDef
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
    """Description of default settings for Pulse systems. These are operations or settings that
    may be good starting points for the Pulse user. The user may modify these defaults through
    the provided methods to build a reference to custom operations, which may in turn be used
    for building Schedules or converting circuits to Schedules.
    """

    def __init__(self, qubit_freq_est, meas_freq_est, buffer,
                 pulse_library, cmd_def, **kwargs):
        """
        Validate and reformat transport layer inputs to initialize this.

        Args:
            qubit_freq_est (list[number]): Estimated qubit frequencies in GHz.
            meas_freq_est (list[number]): Estimated measurement cavity frequencies
                in GHz.
            buffer (int): Default buffer time (in units of dt) between pulses.
            pulse_library (list[PulseLibraryItem]): Pulse name and sample definitions.
            cmd_def (list[Command]): Operation name and definition in terms of Commands.
            **kwargs (Dict[str, Any]]): Other attributes for the super class.
        """
        super().__init__(**kwargs)

        self.buffer = buffer
        self._qubit_freq_est_ghz = qubit_freq_est
        self._meas_freq_est_ghz = meas_freq_est
        self._qubit_freq_est_hz = [freq * 1e9 for freq in qubit_freq_est]
        self._meas_freq_est_hz = [freq * 1e9 for freq in meas_freq_est]
        # TODO: These should be massaged for the user
        self.pulse_library = pulse_library
        self.cmd_def = cmd_def

        # The processed and reformatted circuit operation definitions
        self._ops_def = defaultdict(dict)
        # A backwards mapping from qubit to supported operation
        self._qubit_ops = defaultdict(list)
        # To enable pulse replacement, track where each pulse item is used
        self.__pulse_library_usage = defaultdict(list)

        # Build the above dictionaries from pulse_library and cmd_def
        self.converter = QobjToInstructionConverter(pulse_library, buffer)
        for op in cmd_def:
            qubits = _to_tuple(op.qubits)
            self._qubit_ops[qubits].append(op.name)
            pulse_insts = []
            for inst in op.sequence:
                if inst.name not in ['pv', 'fc', 'acquire', 'snapshot']:
                    self.__pulse_library_usage[inst.name].append(op)
                pulse_insts.append(self.converter(inst))
            self._ops_def[op.name][qubits] = ParameterizedSchedule(*pulse_insts, name=op.name)

    @property
    def qubit_freq_est(self):
        """
        Return the estimated resonant frequency for the given qubit in Hz.

        Returns:
            list[float]: The frequency of the qubit resonance in Hz.
        """
        warnings.warn("The qubit frequency estimation was previously in GHz, and now is in Hz.")
        return self._qubit_freq_est_hz

    @property
    def meas_freq_est(self):
        """
        Return the estimated measurement stimulus frequency to readout from the given qubit.

        Returns:
            list[float]: The measurement stimulus frequency in Hz.
        """
        warnings.warn("The measurement frequency estimation was previously in GHz, "
                      "and now is in Hz.")
        return self._meas_freq_est_hz

    def replace_pulse(self, name, samples):
        """
        Replace the named pulse with the given samples.
        Note: This will update existing operation definitions which are dependent on the
              modified pulse!

        Args:
            name (str): The name of the pulse to replace.
            samples (list(complex)): The complex values to assign to the pulse.
        Returns:
            None
        Raises:
            PulseError: If there was no pulse with the given name by default.
        """
        try:
            self.converter.bind_name.get_bound_method(name)
        except PulseError:
            raise PulseError("Tried to replace pulse '{}' but it is not present in the pulse "
                             "library.".format(name))
        self.converter.bind_pulse(PulseLibraryItem(name=name, samples=samples))
        for op in self.__pulse_library_usage[name]:
            schedule = ParameterizedSchedule(*[self.converter(inst) for inst in op.sequence],
                                             name=op.name)
            self._ops_def[op.name][_to_tuple(op.qubits)] = schedule

    def ops(self):
        """
        Return all operations which are defined. By default, these are typically the basis gates
        along with other operations such as measure and reset.

        Returns:
            list: The names of all the circuit operations which have Schedule definitions in this.
        """
        return list(self._ops_def.keys())

    def op_qubits(self, operation):
        """
        Return a list of the qubits for which the given operation is defined. Single qubit
        operations return a flat list, and multiqubit operations return a list of ordered tuples.

        Args:
            operation (str): The name of the circuit operation.
        Returns:
            list[Union[int, Tuple[int]]]: Qubit indices which have the given operation defined.
                This is a list of tuples if the operation has an arity greater than 1, or a flat
                list of ints otherwise.
        """
        return [qs[0] if len(qs) == 1 else qs
                for qs in sorted(self._ops_def[operation].keys())]

    def qubit_ops(self, qubits):
        """
        Return a list of the operation names that are defined by the backend for the given qubit
        or qubits.

        Args:
            qubits (Union[int, Iterable[int]]): A qubit index, or a list or tuple of indices.
        Returns:
            list[str]: All the operations which are defined on the qubits. For 1 qubit, all the 1Q
                operations defined. For multiple qubits, all the operations which apply to that
                whole set of qubits (e.g. qubits=[0, 1] may return ['cx']).
        """
        return self._qubit_ops[_to_tuple(qubits)]

    def has(self, operation, qubits):
        """
        Is the operation defined for the given qubits?

        Args:
            operation (str): The operation for which to look.
            qubits (list[Union[int, Tuple[int]]]): The specific qubits for the operation.
        Returns:
            bool: True iff the operation is defined.
        """
        return operation in self._ops_def and \
            _to_tuple(qubits) in self._ops_def[operation]

    def assert_has(self, operation, qubits):
        """
        Convenience method to check that the given operation is defined, and error if it is not.

        Args:
            operation (str): The operation for which to look.
            qubits (list[Union[int, Tuple[int]]]): The specific qubits for the operation.
        Returns:
            None
        Raises:
            PulseError: If the operation is not defined on the qubits.
        """
        if not self.has(operation, _to_tuple(qubits)):
            raise PulseError("Operation {op} for qubits {qubits} is not defined for this "
                             "system.".format(op=operation, qubits=qubits))

    def get(self,
            operation,
            qubits,
            *params,
            **kwparams):
        """
        Return the defined Schedule for the given operation on the given qubits.

        Args:
            operation (str): Name of the operation.
            qubits (list[Union[int, Tuple[int]]]): The qubits for the operation.
            *params (list[Union[int, float, complex]]): Command parameters for generating the
                                                        output schedule.
            **kwparams (Dict[str, Union[int, float, complex]]): Keyworded command parameters
                                                                for generating the schedule.
        Returns:
            Schedule: The Schedule defined for the input.

        Raises:
            PulseError: If the operation is not defined on the qubits.
        """
        self.assert_has(operation, qubits)
        schedule = self._ops_def[operation].get(_to_tuple(qubits))
        if isinstance(schedule, ParameterizedSchedule):
            schedule = schedule.bind_parameters(*params, **kwparams)
        return schedule

    def get_parameters(self, operation, qubits):
        """
        Return the list of parameters taken by the given operation on the given qubits.

        Args:
            operation (str): Name of the operation.
            qubits (list[Union[int, Tuple[int]]]): The qubits for the operation.
        Returns:
            Tuple[str]: The parameters required by the operation.

        Raises:
            PulseError: If the operation is not defined on the qubits.
        """
        self.assert_has(operation, qubits)
        return self._ops_def[operation][_to_tuple(qubits)].parameters

    def add(self, operation, qubits, schedule):
        """
        Add a new known operation.

        Args:
            operation (str): The name of the operation to add.
            qubits (list[Union[int, Tuple[int]]]): The qubits which the operation applies to.
            schedule (Schedule): The Schedule that implements the given operation.
        Returns:
            None
        Raises:
            PulseError: If the qubits are provided as an empty iterable.
        """
        qubits = _to_tuple(qubits)
        if qubits == ():
            raise PulseError("Cannot add definition {} with no target qubits.".format(operation))
        if not isinstance(schedule, (Schedule, ParameterizedSchedule)):
            raise PulseError("Attemping to add an invalid schedule type.")
        if self.has(operation, qubits):
            warnings.warn("Replacing previous definition of {} on qubit{} "
                          "{}.".format(operation,
                                       's' if len(qubits) > 1 else '',
                                       qubits if len(qubits) > 1 else qubits[0]))
        self._ops_def[operation][qubits] = schedule

    def remove(self, operation, qubits):
        """Remove the given operation from the defined operations.

        Args:
            operation (str): The name of the operation to add.
            qubits (list[Union[int, Tuple[int]]]): The qubits which the operation applies to.
        Returns:
            None
        Raises:
            PulseError: If the operation is not present.
        """
        self.assert_has(operation, qubits)
        self._ops_def[operation].pop(_to_tuple(qubits))

    def pop(self,
            operation,
            qubits,
            *params,
            **kwparams):
        """
        Remove and return the defined Schedule for the given operation on the given qubits.

        Args:
            operation (str): Name of the operation.
            qubits (list[Union[int, Tuple[int]]]): The qubits for the operation.
            *params (list[Union[int, float, complex]]): Command parameters for generating the
                                                        output schedule.
            **kwparams (Dict[str, Union[int, float, complex]]): Keyworded command parameters
                                                                for generating the schedule.
        Returns:
            Schedule: The Schedule defined for the input.

        Raises:
            PulseError: If command for qubits is not available
        """
        self.assert_has(operation, qubits)
        schedule = self._ops_def[operation].pop(_to_tuple(qubits))
        if isinstance(schedule, ParameterizedSchedule):
            return schedule.bind_parameters(*params, **kwparams)
        return schedule

    def __repr__(self):
        single_qops = "1Q operations:\n"
        multi_qops = "Multi qubit operations:\n"
        for qubits, ops in self._qubit_ops.items():
            if len(qubits) == 1:
                single_qops += "  q{qubit}: {ops}\n".format(qubit=qubits[0], ops=ops)
            else:
                multi_qops += "  {qubits}: {ops}\n".format(qubits=qubits, ops=ops)
        ops = single_qops + multi_qops
        qfreq = "Qubit Frequencies [GHz]\n{freqs}".format(freqs=self._qubit_freq_est_ghz)
        mfreq = "Measurement Frequencies [GHz]\n{freqs} ".format(freqs=self._meas_freq_est_ghz)
        return ("<{name}({ops}{qfreq}\n{mfreq})>"
                "".format(name=self.__class__.__name__, ops=ops, qfreq=qfreq, mfreq=mfreq))

    def cmds(self):
        """
        Deprecated.

        Returns:
            list: The names of all the circuit operations which have Schedule definitions in this.
        """
        warnings.warn("Please use ops() instead of cmds().", DeprecationWarning)
        return self.ops()

    def cmd_qubits(self, cmd_name):
        """
        Deprecated.

        Args:
            cmd_name (str): The name of the circuit operation.
        Returns:
            list[Union[int, Tuple[int]]]: Qubit indices which have the given operation defined.
                This is a list of tuples if the operation has an arity greater than 1, or a flat
                list of ints otherwise.
        """
        warnings.warn("Please use op_qubits() instead of cmd_qubits().", DeprecationWarning)
        return self.op_qubits(cmd_name)

    def build_cmd_def(self):
        """
        Construct the `CmdDef` object for the backend.

        Returns:
            CmdDef: `CmdDef` instance generated from defaults
        """
        warnings.warn("Please use this PulseDefaults instance instead of CmdDef.",
                      DeprecationWarning)
        return CmdDef.from_defaults(self.cmd_def, self.pulse_library, buffer=self.buffer)
