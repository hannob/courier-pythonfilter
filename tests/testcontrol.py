#!/usr/bin/python3
# pythonfilter -- A python framework for Courier global filters
# Copyright (C) 2007-2008  Gordon Messmer <gordon@dragonsdawn.net>
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
import courier.config


courier.config.sysconfdir = 'tmp/configfiles'


import courier.control


message = {}
message['xalias'] = {'control_files': ['tmp/queuefiles/control-xalias'],
                     'control_data': {'e': '',
                                      'f': 'dns; localhost (localhost [127.0.0.1])',
                                      's': 'root@ascension.private.dragonsdawn.net',
                                      'r': [['".xalias/testalias@ascension+2eprivate+2edragonsdawn+2enet"@ascension.private.dragonsdawn.net',
                                             'rfc822;testalias@ascension.private.dragonsdawn.net',
                                             '']],
                                      'U': '',
                                      't': '',
                                      'V': None,
                                      'u': 'local'},
                     'sendersIP': '127.0.0.1'}
message['duplicate'] = {'control_files': ['tmp/queuefiles/control-duplicate'],
                        'control_data': {'e': '',
                                         'f': 'dns; localhost (localhost [127.0.0.1])',
                                         's': 'root@ascension.private.dragonsdawn.net',
                                         'r': [['gordon@ascension.private.dragonsdawn.net',
                                                '',
                                                ''],
                                               ['gordon@ascension.private.dragonsdawn.net',
                                                'rfc822;postmaster@ascension.private.dragonsdawn.net',
                                                '']],
                                         'U': '',
                                         't': '',
                                         'V': None,
                                         'u': 'local'},
                        'sendersIP': '127.0.0.1'}
message['ldapalias'] = {'control_files':  ['tmp/queuefiles/control-ldapalias'],
                        'control_data':{'e': '',
                                        'f': 'dns; localhost (localhost [127.0.0.1])',
                                        's': 'root@ascension.private.dragonsdawn.net',
                                        'r': [['rob@ascension.private.dragonsdawn.net',
                                               '',
                                               'N'],
                                              ['gordon@ascension.private.dragonsdawn.net',
                                               '',
                                               'N']],
                                        'U': '',
                                        't': '',
                                        'V': None,
                                        'u': 'local'},
                        'sendersIP': '127.0.0.1'}
rcpt_a = ['testcontrol@ascension.private.dragonsdawn.net',
          '',
          '']
rcpt_b = ['testcontrol@ascension.private.dragonsdawn.net',
          'testcontrol@dragonsdawn.net',
          'N']


class TestCourierControl(unittest.TestCase):

    def setUp(self):
        os.mkdir('tmp')
        os.system('cp -a queuefiles tmp/queuefiles')
        os.system('cp -a configfiles tmp/configfiles')

    def tearDown(self):
        os.system('rm -rf tmp')

    def testGetLines(self):
        for x in message.values():
            # Deprecated function test
            self.assertEqual(courier.control.getLines(x['control_files'], 's'),
                             [x['control_data']['s']])
            self.assertEqual(courier.control.getLines(x['control_files'], 'f'),
                             [x['control_data']['f']])
            self.assertEqual(courier.control.getLines(x['control_files'], 'e'),
                             [x['control_data']['e']])

            # New function test
            self.assertEqual(courier.control.get_lines(x['control_files'], 's'),
                             [x['control_data']['s']])
            self.assertEqual(courier.control.get_lines(x['control_files'], 'f'),
                             [x['control_data']['f']])
            self.assertEqual(courier.control.get_lines(x['control_files'], 'e'),
                             [x['control_data']['e']])

    def testGetSendersMta(self):
        for x in message.values():
            # Deprecated function test
            self.assertEqual(courier.control.getSendersMta(x['control_files']),
                             x['control_data']['f'])

            # New function test
            self.assertEqual(courier.control.get_senders_mta(x['control_files']),
                             x['control_data']['f'])

    def testGetSendersIP(self):
        for x in message.values():
            # Deprecated function test
            self.assertEqual(courier.control.getSendersIP(x['control_files']),
                             x['sendersIP'])

            # New function test
            self.assertEqual(courier.control.get_senders_ip(x['control_files']),
                             x['sendersIP'])

    def testGetSender(self):
        for x in message.values():
            # Deprecated function test
            self.assertEqual(courier.control.getSender(x['control_files']),
                             x['control_data']['s'])

            # New function test
            self.assertEqual(courier.control.get_sender(x['control_files']),
                             x['control_data']['s'])

    def testGetRecipients(self):
        for x in message.values():
            # Deprecated function test
            self.assertEqual(courier.control.getRecipients(x['control_files']),
                             [y[0] for y in x['control_data']['r']])

            # New function test
            self.assertEqual(courier.control.get_recipients(x['control_files']),
                             [y[0] for y in x['control_data']['r']])

    def testGetRecipientsData(self):
        for x in message.values():
            # Deprecated function test
            self.assertEqual(courier.control.getRecipientsData(x['control_files']),
                             x['control_data']['r'])

            # New function test
            self.assertEqual(courier.control.get_recipients_data(x['control_files']),
                             x['control_data']['r'])

    def testGetControlData(self):
        for x in message.values():
            # Deprecated function test
            self.assertEqual(courier.control.getControlData(x['control_files']),
                             x['control_data'])

            # New function test
            self.assertEqual(courier.control.get_control_data(x['control_files']),
                             x['control_data'])

    def testAddRecipient(self):
        for x in message.values():
            # Deprecated function test
            # FIXME: addRecipient isn't included in the new test here, but it is in
            # testDelRecipient.  To be fixed when backward compatibility is dropped.
            courier.control.addRecipient(x['control_files'],
                                         rcpt_a[0])
            self.assertEqual(courier.control.getRecipientsData(x['control_files']),
                             x['control_data']['r'] + [rcpt_a])

            # New function test
            self.assertEqual(courier.control.get_recipients_data(x['control_files']),
                             x['control_data']['r'] + [rcpt_a])

    def testAddRecipientData(self):
        for x in message.values():
            # Deprecated function test
            # FIXME: addRecipientData isn't included in the new test here, but it is in
            # testDelRecipientData.  To be fixed when backward compatibility is dropped.
            courier.control.addRecipientData(x['control_files'],
                                             rcpt_b)
            self.assertEqual(courier.control.getRecipientsData(x['control_files']),
                             x['control_data']['r'] + [rcpt_b])

            # New function test
            self.assertEqual(courier.control.get_recipients_data(x['control_files']),
                             x['control_data']['r'] + [rcpt_b])

    def testDelRecipient(self):
        for x in message.values():
            # Deprecated function test
            courier.control.addRecipient(x['control_files'],
                                         rcpt_a[0])
            self.assertEqual(courier.control.getRecipientsData(x['control_files']),
                             x['control_data']['r'] + [rcpt_a])
            courier.control.delRecipient(x['control_files'],
                                         rcpt_a[0])
            self.assertEqual(courier.control.getRecipientsData(x['control_files']),
                             x['control_data']['r'])

            # New function test
            courier.control.add_recipient(x['control_files'],
                                          rcpt_a[0])
            self.assertEqual(courier.control.get_recipients_data(x['control_files']),
                             x['control_data']['r'] + [rcpt_a])
            courier.control.del_recipient(x['control_files'],
                                          rcpt_a[0])
            self.assertEqual(courier.control.get_recipients_data(x['control_files']),
                             x['control_data']['r'])

    def testDelRecipientData(self):
        for x in message.values():
            # Deprecated function test
            courier.control.addRecipientData(x['control_files'],
                                             rcpt_b)
            self.assertEqual(courier.control.getRecipientsData(x['control_files']),
                             x['control_data']['r'] + [rcpt_b])
            courier.control.delRecipientData(x['control_files'],
                                             rcpt_b)
            self.assertEqual(courier.control.getRecipientsData(x['control_files']),
                             x['control_data']['r'])

            # New function test
            courier.control.add_recipient_data(x['control_files'],
                                               rcpt_b)
            self.assertEqual(courier.control.get_recipients_data(x['control_files']),
                             x['control_data']['r'] + [rcpt_b])
            courier.control.del_recipient_data(x['control_files'],
                                               rcpt_b)
            self.assertEqual(courier.control.get_recipients_data(x['control_files']),
                             x['control_data']['r'])


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestCourierControl)
    unittest.TextTestRunner(verbosity=2).run(suite)
