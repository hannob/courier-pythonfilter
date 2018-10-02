# courier.control -- python module for handling Courier message control files
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

import ipaddress
import re
import string
import time

from . import config


def get_lines(control_files, key, max_lines=0):
    """Return a list of values in the control_files matching key.

    "key" should be a one character string.  See the "Control Records"
    section of Courier's Mail Queue documentation for a list of valid
    control record keys.

    If the "max_lines" argument is given, it must be a number greater
    than zero.  No more values than indicated by this argument will
    be returned.

    """
    lines = []
    for cf in control_files:
        cfo = open(cf)
        ctl_line = cfo.readline()
        while ctl_line:
            if ctl_line[0] == key:
                lines.append(ctl_line[1:].strip())
                if max_lines and len(lines) == max_lines:
                    break
            ctl_line = cfo.readline()
        if max_lines and len(lines) == max_lines:
            break
    return lines


def get_senders_mta(control_files):
    """Return the "Received-From-MTA" record.

    Courier's documentation indicates that this specifies what goes
    into this header for DSNs generated due to this message.

    """
    sender_lines = get_lines(control_files, 'f', 1)
    if sender_lines:
        return sender_lines[0]
    return None


def get_senders_ip(control_files):
    """Return an IP address if one is found in the "Received-From-MTA" record."""
    sender = get_senders_mta(control_files)
    if not sender:
        return None
    ipstr = sender.partition('[')[2].partition(']')[0]
    if not ipstr:
        return None
    sender_ip = ipaddress.ip_address(ipstr)
    if isinstance(sender_ip, ipaddress.IPv6Address) and sender_ip.ipv4_mapped:
        return str(sender_ip.ipv4_mapped)
    return str(sender_ip)


def get_sender(control_files):
    """Return the envelope sender."""
    sender_lines = get_lines(control_files, 's', 1)
    if sender_lines:
        return sender_lines[0]
    return None


def get_recipients(control_files):
    """Return a list of message recipients.

    This list contains addresses in canonical format, after Courier's
    address rewriting and alias expansion.

    """
    return [x[0] for x in get_recipients_data(control_files)]


def get_recipients_data(control_files):
    """Return a list of lists with details about message recipients.

    Each list in the list returned will have the following elements:
    0: The rewritten address
    1: The "original message recipient", as defined by RFC1891
    2: Zero or more characters indicating DSN behavior.

    """
    recipients_data = []
    for cf in control_files:
        rcpts = _get_recipients_from_file(cf)
        for x in rcpts:
            if x[1] is False:
                recipients_data.append(x[2])
    return recipients_data


def _get_recipients_from_file(control_file):
    """Return a list of lists with details about message recipients.

    Each list in the list returned will have the following elements:
    0: The sequence number of this recipient
    1: Delivery status as either True (delivered) or False (not delivered)
    2: A list containing the following elements, describing this recipient:
        0: The rewritten address
        1: The "original message recipient", as defined by RFC1891
        2: Zero or more characters indicating DSN behavior.

    """

    def _addr(recipients, r):
        if r and r[0]:
            x = [len(recipients), False, r]
            recipients.append(x)

    cfo = open(control_file)
    recipients = []
    r = ['', '', ''] # This list will contain the recipient data.
    ctl_line = cfo.readline()
    while ctl_line:
        if ctl_line[0] == 'r':
            r[0] = ctl_line[1:].strip()
        if ctl_line[0] == 'R':
            r[1] = ctl_line[1:].strip()
        if ctl_line[0] == 'N':
            r[2] = ctl_line[1:].strip()
            # This completes a new record, add it to the recipient data list.
            _addr(recipients, r)
            r = ['', '', '']
        if ctl_line[0] == 'S' or ctl_line[0] == 'F':
            # Control file records either a successful or failed
            # delivery.  Either way, mark this recipient completed.
            rnum = ctl_line.split(' ', 1)[0]
            rnum = int(rnum[1:])
            recipients[rnum][1] = True
        ctl_line = cfo.readline()
    return recipients


def get_control_data(control_files):
    """Return a dictionary containing all of the data that was given to submit.

    The dictionary will have the following elements:
    's': The envelope sender
    'f': The "Received-From-MTA" record
    'e': The envid of this message, as specified in RFC1891, or None
    't': Either 'F' or 'H', specifying FULL or HDRS in the RET parameter
         that was given in the MAIL FROM command, as specified in RFC1891,
         or None
    'V': 1 if the envelope sender address should be VERPed, 0 otherwise
    'U': The security level requested for the message
    'u': The "message source" given on submit's command line
    'r': The list of recipients, as returned by get_recipients_data

    See courier/libs/comctlfile.h in the Courier source code, and the
    submit(8) man page for more information.

    """
    data = {'s': '',
            'f': '',
            'e': None,
            't': None,
            'V': None,
            'U': '',
            'u': None,
            'r': []}
    for cf in control_files:
        cfo = open(cf)
        ctl_line = cfo.readline()
        while ctl_line:
            if ctl_line[0] == 's':
                data['s'] = ctl_line[1:].strip()
            if ctl_line[0] == 'f':
                data['f'] = ctl_line[1:].strip()
            if ctl_line[0] == 'e':
                data['e'] = ctl_line[1:].strip()
            if ctl_line[0] == 't':
                data['t'] = ctl_line[1:].strip()
            if ctl_line[0] == 'V':
                data['V'] = 'V'
            if ctl_line[0] == 'U':
                data['U'] = ctl_line[1:].strip()
            if ctl_line[0] == 'u':
                data['u'] = ctl_line[1:].strip()
            ctl_line = cfo.readline()
    data['r'] = get_recipients_data(control_files)
    return data


def add_recipient(control_files, recipient):
    """Add a recipient to a control_files set.

    The recipient argument must contain a canonical address.  Local
    aliases are not allowed.

    """
    recipient_data = [recipient, '', '']
    add_recipient_data(control_files, recipient_data)


def add_recipient_data(control_files, recipient_data):
    """Add a recipient to a control_files set.

    The recipient_data argument must contain the same information that
    is normally returned by the get_recipients_data function for each
    recipient.  Recipients should be added one at a time.

    """
    # FIXME:  How strict is courier about its upper limit of
    # recipients per control file?  It's easiest to append the
    # recipient to the last control file, but it would be more
    # robust to check the number of recipients in it first and
    # create a new file if necessary.
    if len(recipient_data) != 3:
        raise ValueError('recipient_data must be a list of 3 values.')
    cf = control_files[-1]
    cfo = open(cf, 'a')
    cfo.write('r%s\n' % recipient_data[0])
    cfo.write('R%s\n' % recipient_data[1])
    cfo.write('N%s\n' % recipient_data[2])
    cfo.close()


def _mark_complete(control_file, recipient_index):
    """Mark a single recipient's delivery as completed."""
    cfo = open(control_file, 'a')
    cfo.seek(0, 2) # Seek to the end of the file
    cfo.write('I%d R 250 Ok - Removed by courier.control.py\n' %
              recipient_index)
    cfo.write('S%d %d\n' % (recipient_index, int(time.time())))


def del_recipient(control_files, recipient):
    """Remove a recipient from the list.

    The recipient arg is a canonical address found in one of the
    control files in control_files.

    The first recipient in the control_files that exactly matches
    the address given will be removed by way of marking that delivery
    complete, successfully.

    You should log all such removals so that messages are never
    silently lost.

    """
    for cf in control_files:
        rcpts = _get_recipients_from_file(cf)
        for x in rcpts:
            if(x[1] is False # Delivery is not complete for this recipient
               and x[2][0] == recipient):
                _mark_complete(cf, x[0])
                return


def del_recipient_data(control_files, recipient_data):
    """Remove a recipient from the list.

    The recipient_data arg is a list similar to the data returned by
    get_recipients_data found in one of the control files in
    control_files.

    The first recipient in the control_files that exactly matches
    the data given will be removed by way of marking that delivery
    complete, successfully.

    You should log all such removals so that messages are never
    silently lost.

    """
    if len(recipient_data) != 3:
        raise ValueError('recipient_data must be a list of 3 values.')
    for cf in control_files:
        rcpts = _get_recipients_from_file(cf)
        for x in rcpts:
            if(x[1] is False # Delivery is not complete for this recipient
               and x[2] == recipient_data):
                _mark_complete(cf, x[0])
                return


_hostname = config.me()
_auth_regex = re.compile(r'\((?:IDENT: [^,]*, )?AUTH: \S+ ([^,)]*)(?:, [^)]*)?\)\s*by %s' % _hostname)
def _check_header(header):
    """Search header for _auth_regex.

    If the header is not a "Received" header, return None to indicate
    that scanning should continue.

    If the header is a "Received" header and does not match the regex,
    return 0 to indicate that the filter should stop processing
    headers.

    If the header is a "Received" header and matches the regex, return
    the username used during authentication.

    """
    if header[:9] != 'Received:':
        return None
    found = _auth_regex.search(header)
    if found:
        return found.group(1)
    return 0


def get_auth_user(control_files, body_file=None):
    """Return the username used during SMTP AUTH, if available.

    The return value with be a string containing the username used
    for authentication during submission of the message, or None,
    if authentication was not used.

    The arguments are requested with control_files first in order
    to be more consistent with other functions in this module.
    Courier currently stores auth info only in the message header,
    so body_file will be examined for that information.  Should that
    ever change, and control_files contain the auth info, older
    filters will not break due to changes in this interface.  Filters
    written after such a change in Courier will be able to omit the
    body_file argument.

    """
    try:
        bf_stream = open(body_file)
    except OSError:
        return None
    header = bf_stream.readline()
    while 1:
        bf_line = bf_stream.readline()
        if bf_line == '\n' or bf_line == '':
            # There are no more headers.  Scan the header we've got and quit.
            auth = _check_header(header)
            break
        if bf_line[0] in string.whitespace:
            # This is a continuation line.  Add bf_line to header and loop.
            header += bf_line
        else:
            # This line begins a new header.  Check the previous header and
            # replace it before looping.
            auth = _check_header(header)
            if auth is not None:
                break
            else:
                header = bf_line
    if auth:
        return auth
    return None

# Deprecated names preserved for compatibility with older releases
getLines = get_lines
getSendersMta = get_senders_mta
getSendersIP = get_senders_ip
getSender = get_sender
getRecipients = get_recipients
getRecipientsData = get_recipients_data
getControlData = get_control_data
addRecipient = add_recipient
addRecipientData = add_recipient_data
delRecipient = del_recipient
delRecipientData = del_recipient_data
getAuthUser = get_auth_user
