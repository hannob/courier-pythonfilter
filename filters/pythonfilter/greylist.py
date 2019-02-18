#!/usr/bin/python
# greylist -- Courier filter implementing a "greylisting" technique.
# Copyright (C) 2005-2008  Mickael Marchand <marchand@kde.org>
# Copyright (C) 2006-2008  Georg Lutz <georg-list@georglutz.de>
# Copyright (C) 2006-2008  Gordon Messmer <gordon@dragonsdawn.net>
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

import hashlib
import ipaddress
import sys
import time
import courier.config
import courier.control
from . import ttldb


# The good/bad senders lists will be scrubbed at the interval indicated,
# in seconds, by the senders_purge_interval setting.  Any triplets which
# haven't successfully passed a message will be purged at the age
# indicated by senders_not_passed_ttl.  Any triplets which have passed a
# message will be purged at the age indicated by senders_passed_ttl, and
# will have to prove themselves again.  A triplet must be at as old as
# greylist_time to be accepted.
senders_purge_interval = 60 * 60 * 2
senders_passed_ttl = 60 * 60 * 24 * 36
senders_not_passed_ttl = 60 * 60 * 24
greylist_time = 300


def init_filter():
    courier.config.apply_module_config('greylist.py', globals())
    # Keep a dictionary of sender/recipient/IP triplets that we've seen before
    try:
        global _senders_passed
        global _senders_not_passed
        _senders_passed = ttldb.TtlDb('greylist_Passed', senders_passed_ttl, senders_purge_interval)
        _senders_not_passed = ttldb.TtlDb('greylist_NotPassed',
                                          senders_not_passed_ttl, senders_purge_interval)
    except ttldb.OpenError as e:
        sys.stderr.write('Could not open greylist TtlDb: %s\n' % e)
        sys.exit(1)

    # Record in the system log that this filter was initialized.
    sys.stderr.write('Initialized the "greylist" python filter\n')


def do_filter(body_path, control_paths):
    """Return a temporary failure message if this sender hasn't tried to
    deliver mail previously.

    Search through the control files and discover the envelope sender
    and message recipients.  If the sender has written to these
    recipients before, allow the message.  Otherwise, throw a
    temporary failure, and expect the remote MTA to try again.  Many
    spamware sites and viruses will not, preventing these messages
    from getting into the users' mailbox.

    This strategy is based on the whitepaper at:
    http://projects.puremagic.com/greylisting/whitepaper.html

    """

    senders_ip = ipaddress.ip_address(courier.control.get_senders_ip(control_paths)).exploded
    if '.' in senders_ip:
        # For IPv4, use the first three octets
        senders_ip_network = senders_ip[:senders_ip.rindex('.')]
    else:
        # For IPv6, use the first three hextets
        senders_ip_network = senders_ip[:14]

    # Grab the sender from the control files.
    try:
        sender = courier.control.get_sender(control_paths)
    except:
        return '451 Internal failure locating control files'
    if sender == '':
        # Null sender is allowed as a non-fatal error
        return ''
    sender = sender.lower()

    _senders_passed.purge()
    _senders_not_passed.purge()

    # Create a new MD5 object.  The sender/recipient/IP triplets will
    # be stored in the db in the form of an MD5 digest.
    sender_md5 = hashlib.md5(sender.encode())

    # Create a digest for each triplet and look it up first in the
    # _senders_not_passed db.  If it's found there, but is not old
    # enough to meet greylist_time, save the minimum amount of time
    # the sender must wait before retrying for the error message that
    # we'll return.  If it is old enough, remove the digest from
    # _senders_not_passed db, and save it in the _senders_passed db.
    # Then, check for the triplet in _senders_passed db, and update
    # its time value if found.  If the triplet isn't found in the
    # _senders_passed db, then create a new entry in the
    # _senders_not_passed db, and save the minimum wait time.
    found_all = 1
    biggest_time_to_go = 0

    for recipient in courier.control.get_recipients(control_paths):
        recipient = recipient.lower()

        correspondents = sender_md5.copy()
        correspondents.update(recipient.encode())
        correspondents.update(senders_ip_network.encode())
        cdigest = correspondents.hexdigest()
        _senders_passed.lock()
        _senders_not_passed.lock()
        try:
            if cdigest in _senders_not_passed:
                first_timestamp = float(_senders_not_passed[cdigest])
                time_to_go = first_timestamp + greylist_time - time.time()
                if time_to_go > 0:
                    # The sender needs to wait longer before this delivery is allowed.
                    found_all = 0
                    if time_to_go > biggest_time_to_go:
                        biggest_time_to_go = time_to_go
                else:
                    _senders_passed[cdigest] = time.time()
                    del _senders_not_passed[cdigest]
            elif cdigest in _senders_passed:
                _senders_passed[cdigest] = time.time()
            else:
                found_all = 0
                time_to_go = greylist_time
                if time_to_go > biggest_time_to_go:
                    biggest_time_to_go = time_to_go
                _senders_not_passed[cdigest] = time.time()
        finally:
            _senders_not_passed.unlock()
            _senders_passed.unlock()

    if found_all:
        return ''
    return '451 4.7.1 Greylisting in action, please come back in %s' % \
        time.strftime("%H:%M:%S", time.gmtime(biggest_time_to_go))


if __name__ == '__main__':
    # For debugging, you can create a file that contains one line,
    # beginning with an 's' character, followed by an email address
    # and more lines, beginning with an 'r' character, for each
    # recipient.  Run this script with the name of that file as an
    # argument, and it'll validate that email address.
    if not sys.argv[1:]:
        print('Use: greylist.py <control file>')
        sys.exit(1)
    init_filter()
    print(do_filter('', sys.argv[1:]))
