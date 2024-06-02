#!/usr/bin/python
# pythonfilter -- A python framework for Courier global filters
# Copyright (C) 2008  Gordon Messmer <gordon@dragonsdawn.net>
#
# This file is part of pythonfilter.
#
# pythonfilter is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pythonfilter is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with pythonfilter.  If not, see <http://www.gnu.org/licenses/>.

import os
import shutil
import unittest
import courier.xfilter

test_root = os.path.dirname(__file__)


class TestXfilter(unittest.TestCase):

    def setUp(self):
        os.mkdir(f'{test_root}/tmp')
        shutil.copy(f'{test_root}/queuefiles/control-iso-8859-2', f'{test_root}/tmp')
        shutil.copy(f'{test_root}/queuefiles/data-iso-8859-2', f'{test_root}/tmp')

    def tearDown(self):
        shutil.rmtree(f'{test_root}/tmp')

    def testxfilter(self):
        # Ensure that xfilter can deserialize and serialize a message
        mfilter = courier.xfilter.XFilter('testxfilter',
                                          f'{test_root}/tmp/data-iso-8859-2',
                                          [f'{test_root}/tmp/control-iso-8859-2'])
        submit_val = mfilter.submit()
        self.assertEqual(submit_val, '')

    def testxfilterBpo27321(self):
        # Ensure that xfilter can deserialize and serialize a message
        # containing non-ascii data but no CTE header.
        mfilter = courier.xfilter.XFilter('testxfilter',
                                          f'{test_root}/tmp/data-iso-8859-2',
                                          [f'{test_root}/tmp/control-iso-8859-2'])
        mmsg = mfilter.get_message()
        del mmsg['Content-Transfer-Encoding']
        submit_val = mfilter.submit()
        self.assertEqual(submit_val, '')


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestXfilter)
    unittest.TextTestRunner(verbosity=2).run(suite)
