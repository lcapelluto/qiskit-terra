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

"""A collection of discrete probability metrics."""
import numpy as np


def hellinger_fidelity(dist_p, dist_q):
    """Computes the Hellinger fidelity between
    two counts distributions.

    The fidelity is defined as 1-H where H is the
    Hellinger distance.  This value is bounded
    in the range [0, 1].

    Parameters:
        dist_p (dict): First dict of counts.
        dist_q (dict): Second dict of counts.

    Returns:
        float: Fidelity

    Example:

        .. jupyter-execute::

            from qiskit import QuantumCircuit, execute, BasicAer
            from qiskit.quantum_info.analysis import hellinger_fidelity

            qc = QuantumCircuit(5, 5)
            qc.h(2)
            qc.cx(2, 1)
            qc.cx(2, 3)
            qc.cx(3, 4)
            qc.cx(1, 0)
            qc.measure(range(5), range(5))

            sim = BasicAer.get_backend('qasm_simulator')
            res1 = execute(qc, sim).result()
            res2 = execute(qc, sim).result()

            hellinger_fidelity(res1.get_counts(), res2.get_counts())
    """
    p_sum = sum(dist_p.values())
    q_sum = sum(dist_q.values())

    p_normed = {}
    for key, val in dist_p.items():
        p_normed[key] = val/p_sum

    q_normed = {}
    for key, val in dist_q.items():
        q_normed[key] = val/q_sum

    total = 0
    for key, val in p_normed.items():
        if key in q_normed.keys():
            total += (np.sqrt(val) - np.sqrt(q_normed[key]))**2
            del q_normed[key]
        else:
            total += val
    total += sum(q_normed.values())

    dist = np.sqrt(total)/np.sqrt(2)

    return 1-dist
