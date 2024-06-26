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
import unittest
import shutil
import time
import courier.config
from filters.pythonfilter import ttldb


class TestTtlDb(unittest.TestCase):

    def setUp(self):
        os.mkdir(f'{os.path.dirname(__file__)}/tmp')
        os.mkdir(f'{os.path.dirname(__file__)}/tmp/pythonfilter')

    def tearDown(self):
        shutil.rmtree(f'{os.path.dirname(__file__)}/tmp')

    def testdbm(self):
        courier.config._standard_config_paths = f'{os.path.dirname(__file__)}/configfiles/pythonfilter-modules.conf'
        db = ttldb.TtlDb('testTtlDb', 1, 1)
        db.purge()
        db.lock()
        value1 = time.time()
        db['name1'] = value1
        db.unlock()
        self.assertEqual('name1' in db, True)
        self.assertEqual(int(db['name1']), int(value1))
        time.sleep(2)
        value2 = time.time()
        db['name2'] = value2
        db['name2\' -- '] = value2
        time.sleep(1)
        value2 = time.time()
        db['name2'] = value2
        db['name2\' -- '] = value2
        db.purge()
        self.assertEqual('name1' in db, False)
        self.assertEqual('name2' in db, True)
        self.assertEqual(int(db['name2']), int(value2))
        self.assertEqual(int(db['name2\' -- ']), int(value2))


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestTtlDb)
    unittest.TextTestRunner(verbosity=2).run(suite)
