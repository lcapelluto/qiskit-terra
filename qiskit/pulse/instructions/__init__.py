# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2020.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""
Building Pulse Instructions
===========================

Pulse programs, which are called :py:class:`~qiskit.pulse.Schedule` s, describe instruction
sequences for the control electronics.

On this page, we will cover in depth these ``Instruction``\ s available
through Qiskit Pulse:

-  `Delay(duration: int, channel) <#delay>`__
-  `Play(pulse, channel) <#play>`__
-  `SetFrequency(frequency, channel) <#frequency>`__
-  `ShiftPhase(phase, channel) <#phase>`__
-  `Acquire(duration, channel, mem_slot, reg_slot) <#acquire>`__

Each instruction type has its own set of operands. As you can see above,
they each include at least one ``Channel`` to specify where the
instruction will be applied.

**Channels** are labels for signal lines from the control hardware to
the quantum chip.

-  :py:class:`~qiskit.pulse.channels.DriveChannel`\ s are typically used for *driving* single qubit
   rotations,
-  :py:class:`~qiskit.pulse.channels.ControlChannel`\ s are typically used for multi-qubit gates or
   additional drive lines for tunable qubits,
-  :py:class:`~qiskit.pulse.channels.MeasureChannel`\ s are specific to transmitting pulses which
   stimulate readout, and
-  :py:class:`~qiskit.pulse.channels.AquireChannel`\ s are used to trigger digitizers which collect
   readout signals.

:py:class:`~qiskit.pulse.channels.DriveChannel`\ s,
:py:class:`~qiskit.pulse.channels.ControlChannel`\ s, and
:py:class:`~qiskit.pulse.channels.MeasureChannel`\ s
are all :py:class:`~qiskit.pulse.channels.PulseChannel`\ s; this means
that they support *transmitting* pulses, whereas the
:py:class:`~qiskit.pulse.channels.AcquireChannel` is a receive channel only and
cannot play waveforms.

For the following examples, we will create one
:py:class:`~qiskit.pulse.channels.DriveChannel` instance
for each :py:class:`~qiskit.pulse.instruction.Instruction` that accepts a
:py:class:`~qiskit.pulse.channels.PulseChannel`. Channels take
one integer ``index`` argument. Except for
:py:class:`~qiskit.pulse.channels.ControlChannel`\ s, the
index maps trivially to the qubit label.

.. code:: ipython3

    from qiskit.pulse import DriveChannel

    channel = DriveChannel(0)

:py:class:`~qiskit.pulse.instructions.Delay`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

One of the simplest instructions we can build is ``Delay``. This is a
blocking instruction that tells the control electronics to output no
signal on the given channel for the duration specified. It is useful for
controlling the timing of other instructions.

The duration here and elsewhere is in terms of the backend’s cycle time
(1 / sample rate), ``dt``.

To build a ``Delay`` instruction, we pass the duration and channel:

.. code:: ipython3

    from qiskit.pulse import Delay

    delay_5dt = Delay(5, channel)

where ``channel`` can be any kind of channel, including
``AcquireChannel``.

That’s all there is to it. This instruction, ``delay_5dt``, is ready to
be included in a ``Schedule``. Any instruction appended after
``delay_5dt`` on the same channel will execute five timesteps later than
it would have without this delay.

:py:class:`~qiskit.pulse.instructions.Play`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``Play`` instruction is responsible for executing *pulses*. It’s
straightforward to build one:

::

   play = Play(pulse, channel)

Let’s clarify what the ``pulse`` argument is and explore a few different
ways to build one.

Pulses
^^^^^^

A ``Pulse`` specifies an arbitrary pulse *envelope*. The modulation
frequency and phase of the output waveform are controlled by the
``SetFrequency`` and ``ShiftPhase`` instructions, which we will cover
next.

The image below may provide some intuition for why they are specified
separately. Think of the pulses which describe their envelopes as input
to an arbitrary waveform generator (AWG), a common lab instrument – this
is depicted in the left image. Notice the limited sample rate
discritizes the signal. The signal produced by the AWG may be mixed with
a continuous sine wave generator. The frequency of its output is
controlled by instructions to the sine wave generator; see the middle
image. Finally, the signal sent to the qubit is demonstrated by the
right side of the image below.

**Note**: The hardware may be implemented in other ways, but if we keep
the instructions separate, we avoid losing explicit information, such as
the value of the modulation frequency.

.. figure:: ../../docs/source_images/pulse_imgs/pulse_modulation.png
   :alt: Pulse modulation image

   alt text

There are many methods available to us for building up pulses. Our
``pulse_lib`` within Qiskit Pulse contains helpful methods for building
``Pulse``\ s. Let’s take for example a simple Gaussian pulse – a pulse
with its envelope described by a sampled Gaussian function. We
arbitrarily choose an amplitude of 1, standard deviation :math:`\sigma`
of 10, and 128 sample points.

**Note**: The maximum amplitude allowed is ``1.0``. Most systems also
have additional constraints on the minimum and maximum number of samples
allowed in a pulse. These additional constraints, if available, would be
provided through the ``BackendConfiguration`` which is described
`here <gathering_system_information.ipynb#Configuration>`__.

.. code:: ipython3

    from qiskit.pulse import pulse_lib

    amp = 1
    sigma = 10
    num_samples = 128

**Parametric pulses**

Let’s build our Gaussian pulse using the ``Gaussian`` parametric pulse.
A parametric pulse sends the name of the function and its parameters to
the backend, rather than every individual sample. Using parametric
pulses makes the jobs you send to the backend much smaller. IBM Quantum
backends limit the maximum job size that they accept, so parametric
pulses may allow you to run larger programs.

Other parametric pulses in the ``pulse_lib`` include ``GaussianSquare``,
``Drag``, and ``ConstantPulse``.

**Note**: The backend is responsible for deciding exactly how to sample
the parametric pulses. It is possible to draw parametric pulses, but the
samples displayed are not guaranteed to be the same as those executed on
the backend.

.. code:: ipython3

    pulse = pulse_lib.Gaussian(num_samples, amp, sigma)
    pulse.draw()




.. image:: ../../docs/source_images/pulse_imgs/building_pulse_instructions_7_0.png



**Sample pulses**

It is also possible to specify the waveform as an array of samples. We
pass the samples to a ``SamplePulse``.

.. code:: ipython3

    import numpy as np

    times = np.arange(num_samples)
    gaussian_samples = np.exp(-1/2 *((times - num_samples / 2) ** 2 / sigma**2))

    pulse = pulse_lib.SamplePulse(gaussian_samples)
    pulse.draw()




.. image:: ../../docs/source_images/pulse_imgs/building_pulse_instructions_9_0.png



**Pulse library functions**

Our own pulse library has sampling methods to build ``SamplePulse``\ s
from common waveforms.

.. code:: ipython3

    pulse = pulse_lib.gaussian(duration=num_samples, amp=amp, sigma=sigma)
    pulse.draw()




.. image:: ../../docs/source_images/pulse_imgs/building_pulse_instructions_11_0.png



**External libraries**


Alternatively, you can make use of an external library.

.. code:: ipython3

    from scipy import signal

    sampled_gaussian_envelope = signal.gaussian(num_samples, sigma)
    pulse = pulse_lib.SamplePulse(sampled_gaussian_envelope)
    pulse.draw()




.. image:: ../../docs/source_images/pulse_imgs/building_pulse_instructions_13_0.png



Regardless of which method you use to specify your ``pulse``, ``Play``
is instantiated the same way:

.. code:: ipython3

    from qiskit.pulse import Play


    play_gaus = Play(pulse, channel)

The ``Play`` instruction gets its duration from its ``Pulse``: the
duration of a parametrized pulse is an explicit argument, and the
duration of a ``SamplePulse`` is the number of input samples.

:py:class:`~qiskit.pulse.instructions.SetFrequency`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

As explained previously, the output pulse waveform envelope is also
modulated by a frequency and phase. Each channel has a `default
frequency listed in the
``backend.defaults()`` <gathering_system_information.ipynb#Defaults>`__.

The frequency of a channel can be updated at any time within a
``Schedule`` by the ``SetFrequency`` instruction. It takes a float
``frequency`` and a ``PulseChannel`` ``channel`` as input. All pulses on
a channel following a ``SetFrequency`` instruction will be modulated by
the given frequency until another ``SetFrequency`` instruction is
encountered or until the program ends.

The instruction has an implicit duration of ``0``.

**Note**: The frequencies that can be requested are limited by the total
bandwidth and the instantaneous bandwidth of each hardware channel. In
the future, these will be reported by the ``backend``.

.. code:: ipython3

    from qiskit.pulse import SetFrequency

    set_freq = SetFrequency(4.5e9, channel)

:py:class:`~qiskit.pulse.instructions.ShiftPhase`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``ShiftPhase`` instruction will increase the phase of the frequency
modulation by ``phase``. Like ``SetFrequency``, this phase shift will
affect all following instructions on the same channel until the program
ends. To undo the affect of a ``ShiftPhase``, the negative ``phase`` can
be passed to a new instruction.

Like ``SetFrequency``, the instruction has an implicit duration of
``0``.

.. code:: ipython3

    from qiskit.pulse import ShiftPhase

    phase_pi = ShiftPhase(np.pi, channel)

:py:class:`~qiskit.pulse.instructions.Acquire`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``Acquire`` instruction triggers data acquisition for readout. It
takes a duration, an ``AcquireChannel`` which maps to the qubit being
measured, and a ``MemorySlot`` or a ``RegisterSlot``. The ``MemorySlot``
is classical memory where the readout result will be stored. The
``RegisterSlot`` maps to a register in the control electronics which
stores the readout result for fast feedback.

``Acquire`` instructions can also take custom ``Discriminator``\ s and
``Kernel``\ s as keyword arguments. Read more about building
measurements `here <adding_measurements.ipynb>`__.

.. code:: ipython3

    from qiskit.pulse import Acquire, AcquireChannel, MemorySlot

    acquire = Acquire(1200, AcquireChannel(0), MemorySlot(0))

Now that we know how to build instructions, let’s learn how to compose
them into ``Schedule``\ s on the `next
page <building_pulse_schedules.ipynb>`__!


``Instructions`` API Docs
=========================

The ``instruction`` module holds the various ``Instruction`` s which are supported by
Qiskit Pulse. Instructions have operands, which typically include at least one
:py:class:`~qiskit.pulse.channels.Channel` specifying where the instruction will be applied.

Every instruction has a duration, whether explicitly included as an operand or implicitly defined.
For instance, a :py:class:`~qiskit.pulse.instructions.ShiftPhase` instruction can be instantiated
with operands *phase* and *channel*, for some float ``phase`` and a
:py:class:`~qiskit.pulse.channels.Channel` ``channel``::

    ShiftPhase(phase, channel)

The duration of this instruction is implicitly zero. On the other hand, the
:py:class:`~qiskit.pulse.instructions.Delay` instruction takes an explicit duration::

    Delay(duration, channel)

An instruction can be added to a :py:class:`~qiskit.pulse.Schedule`, which is a
sequence of scheduled Pulse ``Instruction`` s over many channels. ``Instruction`` s and
``Schedule`` s implement the same interface.

.. autosummary::
   :toctree: ../stubs/

   Acquire
   Delay
   Play
   SetFrequency
   ShiftFrequency
   SetPhase
   ShiftPhase
   Snapshot

Abstract Classes
~~~~~~~~~~~~~~~~
.. autosummary::
   :toctree: ../stubs/

   Instruction

"""
from .acquire import Acquire
from .delay import Delay
from .directives import Directive, RelativeBarrier
from .instruction import Instruction
from .frequency import SetFrequency, ShiftFrequency
from .phase import ShiftPhase, SetPhase
from .play import Play
from .snapshot import Snapshot
