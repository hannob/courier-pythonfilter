#!/usr/bin/python
# dialback -- Courier filter which verifies sender addresses by contacting their MX
# Copyright (C) 2003-2008  Gordon Messmer <gordon@dragonsdawn.net>
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
import smtplib
import socket
import sys
import time
import DNS
import courier.config
from . import ttldb


# The good/bad senders lists will be scrubbed at the interval indicated
# in seconds.  All records older than the "TTL" number of seconds
# will be removed from the lists.
senders_ttl = 60 * 60 * 24 * 7
senders_purge_interval = 60 * 60 * 12

# SMTP conversation timeout in seconds.  Setting this too low will
# lead to 4XX failures.
smtp_timeout = 60

# The postmaster address will be used for the "MAIL" command in the
# dialback conversation.  You can set this to a zero-length string,
# instead, in which case you'll refuse mail when the sender's mail
# server doesn't accept DSNs, as it is required to by RFC.
postmaster_addr = 'postmaster@%s' % courier.config.me()


def init_filter():
    courier.config.apply_module_config('dialback.py', globals())
    # Keep a dictionary of authenticated senders to avoid more work than
    # required.
    try:
        global _good_senders
        global _bad_senders
        _good_senders = ttldb.TtlDb('goodsenders', senders_ttl, senders_purge_interval)
        _bad_senders = ttldb.TtlDb('badsenders', senders_ttl, senders_purge_interval)
    except ttldb.OpenError as e:
        sys.stderr.write('Could not open dialback TtlDb: %s\n' % e)
        sys.exit(1)
    # Initialize the DNS module
    DNS.DiscoverNameServers()
    # Record in the system log that this filter was initialized.
    sys.stderr.write('Initialized the dialback python filter\n')


def do_filter(body_path, control_paths):
    """Contact the MX for this message's sender and validate their address.

    Validation will be done by starting an SMTP session with the MX and
    checking the server's reply to a RCPT command with the sender's address.

    """

    # Grab the sender from the control files.
    try:
        sender = courier.control.get_sender(control_paths)
    except:
        return '451 Internal failure locating control files'
    if sender == '':
        # Null sender is allowed as a non-fatal error
        return ''
    sender_md5 = hashlib.md5(sender.encode()).hexdigest()

    _good_senders.purge()
    _bad_senders.purge()
    # If this sender is known already, then we don't actually need to do the
    # dialback.  Update the timestamp in the dictionary and then return the
    # status.
    _good_senders.lock()
    try:
        if sender_md5 in _good_senders:
            _good_senders[sender_md5] = time.time()
            # Lock will be released in "finally" clause.
            return ''
    finally:
        _good_senders.unlock()
    _bad_senders.lock()
    try:
        if sender_md5 in _bad_senders:
            _bad_senders[sender_md5] = time.time()
            # Lock will be released in "finally" clause.
            return '517 Sender does not exist: %s' % sender
    finally:
        _bad_senders.unlock()

    # The sender is new, so break the address into name and domain parts.
    try:
        (sender_name, sender_domain) = sender.split('@')
    except:
        # Pretty sure this can't happen...
        return '501 Envelope sender is invalid'

    # Look up the MX records for this sender's domain in DNS.  If none are
    # found, then check the domain for an A record, and dial back to that
    # host.  If no A record is found, then perhaps the message is a DSN...
    # Just return a success code if no MX and no A records are found.
    try:
        mx_list = DNS.mxlookup(sender_domain)
        if not mx_list:
            if socket.getaddrinfo(sender_domain, 'smtp'):
                # put this host in the mx_list and continue
                mx_list.append((1, sender_domain))
            else:
                # no record was found
                return ''
    except:
        # Probably a DNS timeout...
        # Also should never happen, because courier's smtpd should have
        # just validated this domain.
        return '421 DNS failure resolving %s' % sender_domain

    # Loop through the dial-back candidates and ask each one to validate
    # the address that we got as the sender.  If they return a success
    # code to the RCPT command, then we accept the mail.  If they return
    # any 5XX code, we refuse the incoming mail with a 5XX error, as well.
    # If no SMTP server is available, or all report 4XX errors, we'll
    # give a 4XX error to the sender.

    # Unless we get a satisfactory responce from a server, we'll use
    # this as the filer status.
    filter_reply = '421 No SMTP servers were available to authenticate sender'

    for mx in mx_list:
        # Create an SMTP instance.  If the dialback thread takes
        # too long, we'll close its socket.
        smtpi = smtplib.SMTP()
        try:
            smtpi.connect(mx[1])
        except:
            filter_reply = '400 SMTP class exception during connect'
            continue

        try:
            (code, reply) = smtpi.helo(courier.config.esmtphelo(smtpi.sock))
            if code // 100 != 2:
                # Save the error message.  If no other servers are available,
                # inform the sender, but don't save the sender as bad.
                filter_reply = '421 %s rejected the HELO command' % mx[1]
                smtpi.close()
                continue
        except:
            filter_reply = '400 SMTP class exception during HELO'
            continue

        try:
            (code, reply) = smtpi.mail(postmaster_addr)
            if code // 100 != 2:
                # Save the error message.  If no other servers are available,
                # inform the sender, but don't save the sender as bad.
                filter_reply = '421 %s rejected the MAIL FROM command' % mx[1]
                smtpi.close()
                continue
        except:
            filter_reply = '400 SMTP class exception during MAIL command'
            continue

        try:
            (code, reply) = smtpi.rcpt(sender)
            if code // 100 == 2:
                # Success!  Mark this user good, and stop testing.
                _good_senders.lock()
                try:
                    _good_senders[sender_md5] = time.time()
                finally:
                    _good_senders.unlock()
                filter_reply = ''
                break
            elif code // 100 == 5:
                # Mark this user bad and stop testing.
                _bad_senders.lock()
                try:
                    _bad_senders[sender_md5] = time.time()
                finally:
                    _bad_senders.unlock()
                filter_reply = ('517-MX server %s said:\n'
                                '517 Sender does not exist: %s' % (mx[1], sender))
                break
            else:
                # Save the error message, but try to find a server that will
                # provide a better answer.
                filter_reply = ('421-Unable to validate sender address.'
                                '421 MX server %s provided unknown reply\n' % (mx[1]))
            smtpi.quit()
        except:
            filter_reply = '400 SMTP class exception during RCPT command'
            continue
    return filter_reply


if __name__ == '__main__':
    # For debugging, you can create a file that contains just one
    # line, beginning with an 's' character, followed by an email
    # address.  Run this script with the name of that file as an
    # argument, and it'll validate that email address.
    if not sys.argv[1:]:
        print('Use:  dialback.py <control file>')
        sys.exit(1)
    init_filter()
    print(do_filter('', sys.argv[1:]))
