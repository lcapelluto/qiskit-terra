# This code is part of Qiskit.
#
# (C) Copyright IBM 2017, 2020.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""A test for circuit tools"""
import unittest

from test import combine
from ddt import ddt
from numpy import pi
from qiskit.test import QiskitTestCase
from qiskit.circuit.tools.pi_check import pi_check
from qiskit.circuit import Parameter


@ddt
class TestPiCheck(QiskitTestCase):
    """ qiskit/visualization/tools/pi_check.py """

    @combine(case=[(3.14, '3.14'),
                   (3.141592653589793, 'pi'),
                   (6.283185307179586, '2pi'),
                   (2.99, '2.99'),
                   (2.999999999999999, '3'),
                   (0.99, '0.99'),
                   (0.999999999999999, '1'),
                   (pi, 'pi'),
                   (-pi, '-pi'),
                   (3*pi, '3pi'),
                   (-3*pi, '-3pi'),
                   (pi/35, 'pi/35'),
                   (-pi/35, '-pi/35'),
                   (3*pi/35, '0.26928'),
                   (-3*pi/35, '-0.26928'),
                   (pi**2, 'pi**2'),
                   (-pi**2, '-pi**2'),
                   (1e9, '1e+09'),
                   (-1e9, '-1e+09'),
                   (1e-9, '1e-09'),
                   (-1e-9, '-1e-09'),
                   (6*pi/11, '6pi/11'),
                   (-6*pi/11, '-6pi/11'),
                   (6*pi/1, '6pi'),
                   (-6*pi/1, '-6pi'),
                   (6*pi/2, '3pi'),
                   (-6*pi/2, '-3pi'),
                   (1j*3/(7*pi), '3/7pij'),
                   (-1j*3/(7*pi), '-3/7pij'),
                   (6*pi/5+1j*3*pi/7, '6pi/5+3pi/7j'),
                   (-6*pi/5+1j*3*pi/7, '-6pi/5+3pi/7j'),
                   (6*pi/5-1j*3*pi/7, '6pi/5-3pi/7j'),
                   (-6*pi/5-1j*3*pi/7, '-6pi/5-3pi/7j'),
                   (1/pi, '1/pi'),
                   (-1/pi, '-1/pi'),
                   (6/(5*pi), '6/5pi'),
                   (-6/(5*pi), '-6/5pi'),
                   (-382578.0+.0234567j, '-3.8258e+05+0.023457j'),
                   (-382578.0-.0234567j, '-3.8258e+05-0.023457j')
                   ])
    def test_default(self, case):
        """Default pi_check({case[0]})='{case[1]}'"""
        input_number = case[0]
        expected_string = case[1]
        result = pi_check(input_number)
        self.assertEqual(result, expected_string)

    def test_params(self):
        """Test pi_check with Parameters"""
        x = Parameter('x')
        y = Parameter('y')
        z = Parameter('z')
        pcase = (pi**3 * x + 3/(4*pi) * y - 13*pi/2 * z, 'pi**3*x + 3/4pi*y - 13pi/2*z')
        input_number = pcase[0]
        expected_string = pcase[1]
        result = pi_check(input_number)
        self.assertEqual(result, expected_string)


if __name__ == '__main__':
    unittest.main(verbosity=2)
