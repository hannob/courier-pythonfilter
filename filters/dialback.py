#!/usr/bin/python
# dialback -- Courier filter which verifies sender addresses by contacting their MX
# Copyright (C) 2006  Gordon Messmer <gordon@dragonsdawn.net>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import DNS
import anydbm
import os
import select
import smtplib
import socket
import string
import sys
import thread
import time
import courier.config


# Keep a dictionary of authenticated senders to avoid more work than
# required.
_sendersLock = thread.allocate_lock()
_sendersDir = '/var/state/pythonfilter'
try:
    _goodSenders = anydbm.open(_sendersDir + '/goodsenders', 'c')
    _badSenders = anydbm.open(_sendersDir + '/badsenders', 'c')
except:
    sys.stderr.write('Failed to open db in %s, make sure that it exists\n' % _sendersDir)
    sys.exit(1)

# The good/bad senders lists will be scrubbed at the interval indicated
# in seconds.  All records older than the "TTL" number of seconds
# will be removed from the lists.
_sendersLastPurged = 0
_sendersTTL = 60 * 60 * 24 * 7
_sendersPurgeInterval = 60 * 60 * 12

# SMTP conversation timeout in seconds.  Setting this too low will
# lead to 4XX failures.
_smtpTimeout = 60

# Initialize the DNS module
DNS.DiscoverNameServers()

# The postmaster address will be used for the "MAIL" command in the
# dialback conversation.
postmasterAddr = 'postmaster@%s' % courier.config.me()

# Record in the system log that this filter was initialized.
sys.stderr.write('Initialized the dialback python filter\n')


def _lockDB():
    _sendersLock.acquire()


def _unlockDB():
    # Synchronize the database to disk if the db type supports that
    try:
        _goodSenders.sync()
        _badSenders.sync()
    except AttributeError:
        # this dbm library doesn't support the sync() method
        pass
    _sendersLock.release()


def doFilter(bodyFile, controlFileList):
    """Contact the MX for this message's sender and validate their address.

    Validation will be done by starting an SMTP session with the MX and
    checking the server's reply to a RCPT command with the sender's address.

    """

    global _sendersLastPurged

    try:
        # The envelope sender will always be the first record in the control
        # files, according to the courier documentation.  Open the first file,
        # read the first line, and if it isn't the sender record, return
        # a failure response.
        ctlfile = open(controlFileList[0])
        ctlline = ctlfile.readline()
    except:
        return '451 Internal failure locating control files'

    if ctlline[0] != 's':
        return '451 Internal failure locating envelope sender record'
    if len(ctlline) == 2:
        # Null sender is allowed as a non-fatal error
        return ''

    sender = string.strip(ctlline[1:])

    # If this sender is known already, then we don't actually need to do the
    # dialback.  Update the timestamp in the dictionary and then return the
    # status.
    _lockDB()
    # Scrub the lists if it is time to do so.
    if time.time() > (_sendersLastPurged + _sendersPurgeInterval):
        minAge = time.time() - _sendersTTL
        for key in _goodSenders.keys():
            if float(_goodSenders[key]) < minAge:
                del _goodSenders[key]
        for key in _badSenders.keys():
            if float(_badSenders[key]) < minAge:
                del _badSenders[key]
        _sendersLastPurged = time.time()
    if _goodSenders.has_key(sender):
        _goodSenders[sender] = str(time.time())
        _unlockDB()
        return ''
    if _badSenders.has_key(sender):
        _badSenders[sender] = str(time.time())
        _unlockDB()
        return '517 Sender does not exist: %s' % sender
    _unlockDB()

    # The sender is new, so break the address into name and domain parts.
    try:
        (senderName, senderDomain) = string.split(sender , '@')
    except:
        # Pretty sure this can't happen...
        return '501 Envelope sender is invalid'

    # Look up the MX records for this sender's domain in DNS.  If none are
    # found, then check the domain for an A record, and dial back to that
    # host.  If no A record is found, then perhaps the message is a DSN...
    # Just return a success code if no MX and no A records are found.
    try:
        mxList = DNS.mxlookup(senderDomain)
        if mxList == []:
            if socket.getaddrinfo(senderDomain, 'smtp'):
                # put this host in the mxList and continue
                mxList.append((1, senderDomain))
            else:
                # no record was found
                return ''
    except:
        # Probably a DNS timeout...
        # Also should never happen, because courier's smtpd should have
        # just validated this domain.
        return '421 DNS failure resolving %s' % senderDomain

    # Loop through the dial-back candidates and ask each one to validate
    # the address that we got as the sender.  If they return a success
    # code to the RCPT command, then we accept the mail.  If they return
    # any 5XX code, we refuse the incoming mail with a 5XX error, as well.
    # If no SMTP server is available, or all report 4XX errors, we'll
    # give a 4XX error to the sender.

    # Unless we get a satisfactory responce from a server, we'll use
    # this as the filer status.
    filterReply = '421 No SMTP servers were available to authenticate sender'

    for MX in mxList:
        # Create an SMTP instance.  If the dialback thread takes
        # too long, we'll close its socket.
        smtpi = ThreadSMTP()
        try:
            smtpi.connect(MX[1])
            (code, reply) = smtpi.helo()
            if code // 100 != 2:
                # Save the error message.  If no other servers are available,
                # inform the sender, but don't save the sender as bad.
                filterReply = '421 %s rejected the HELO command' % MX[1]
                smtpi.close()
                continue
    
            (code, reply) = smtpi.mail(postmasterAddr)
            if code // 100 != 2:
                # Save the error message.  If no other servers are available,
                # inform the sender, but don't save the sender as bad.
                filterReply = '421 %s rejected the MAIL FROM command' % MX[1]
                smtpi.close()
                continue
    
            (code, reply) = smtpi.rcpt(sender)
            if code // 100 == 2:
                # Success!  Mark this user good, and "break" to stop testing.
                _lockDB()
                _goodSenders[sender] = str(time.time())
                _unlockDB()
                filterReply = ''
                break
            elif code // 100 == 5:
                # Mark this user bad and stop testing.
                _lockDB()
                _badSenders[sender] = str(time.time())
                _unlockDB()
                filterReply = '517-MX server %s said:\n' \
                              '517 Sender does not exist: %s' % (MX[1], sender)
                break
            else:
                # Save the error message, but try to find a server that will
                # provide a better answer.
                filterReply = '421-Unable to validate sender address.' \
                              '421 MX server %s provided unknown reply\n' % (MX[1])
            smtpi.quit()
        except:
            filterReply = '400 SMTP class exception'
    return filterReply


class ThreadSMTP(smtplib.SMTP):
    """SMTP class safe for use in threaded applications.
    
    This class reimplements the SMTP class with non-blocking IO,
    so that threaded applications don't lock up.
    
    This class won't make starttls support thread-safe.
    """
    def connect(self, host='localhost', port=0):
        """Connect to a host on a given port.

        If the hostname ends with a colon (`:') followed by a number, and
        there is no port specified, that suffix will be stripped off and the
        number interpreted as the port number to use.

        Note: This method is automatically invoked by __init__, if a host is
        specified during instantiation.

        """
        if not port and (host.find(':') == host.rfind(':')):
            i = host.rfind(':')
            if i >= 0:
                host, port = host[:i], host[i+1:]
                try: port = int(port)
                except ValueError:
                    raise socket.error, "nonnumeric port"
        if not port: port = smtplib.SMTP_PORT
        if self.debuglevel > 0: print>>stderr, 'connect:', (host, port)
        msg = "getaddrinfo returns an empty list"
        self.sock = None
        for res in socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM):
            af, socktype, proto, canonname, sa = res
            try:
                self.sock = socket.socket(af, socktype, proto)
                self.sock.setblocking(0)
                if self.debuglevel > 0: print>>stderr, 'connect:', (host, port)
                # Try to connect to the non-blocking socket.  We expect connect()
                # to throw an error, indicating that the connection is in progress.
                # Use select to wait for the connection to complete, and then call
                # connect() again to complete the connection.
                try:
                    self.sock.connect(sa)
                except socket.error:
                    readySocks = select.select([self.sock], [], [], _smtpTimeout)
                    if not readySocks[0]:
                        # The connection timed out.
                        print>>stderr, 'connect fail:', (host, port)
                        if self.sock:
                            self.sock.close()
                        self.sock = None
                    else:
                        self.sock.connect(sa)
            except socket.error, msg:
                if self.debuglevel > 0: print>>stderr, 'connect fail:', (host, port)
                if self.sock:
                    self.sock.close()
                self.sock = None
                continue
            break
        if not self.sock:
            raise socket.error, msg
        (code, msg) = self.getreply()
        if self.debuglevel > 0: print>>stderr, "connect:", msg
        return (code, msg)


    def send(self, str):
        """Send `str' to the server."""
        if self.debuglevel > 0: print>>stderr, 'send:', repr(str)
        if self.sock:
            try:
                # Loop: Wait for select() to indicate that the socket is ready
                # for data, and call send().  If send returns a value smaller
                # than the total length of str, save the remaining data, and
                # continue to attempt to send it.  If select() times out, raise
                # an exception and let the handler close the connection.
                while str:
                    readySocks = select.select([], [self.sock], [], _smtpTimeout)
                    if not readySocks[1]:
                        raise socket.error, 'Write timed out.'
                    sent = self.sock.send(str)
                    if sent < len(str):
                        str = str[sent:]
                    else:
                        # All the data was written, break the loop.
                        break
            except socket.error:
                self.close()
                raise smtplib.SMTPServerDisconnected('Server not connected')
        else:
            raise smtplib.SMTPServerDisconnected('please run connect() first')


    def getreply(self):
        """Get a reply from the server.

        Returns a tuple consisting of:

          - server response code (e.g. '250', or such, if all goes well)
            Note: returns -1 if it can't read response code.

          - server response string corresponding to response code (multiline
            responses are converted to a single, multiline string).

        Raises SMTPServerDisconnected if end-of-file is reached.
        """
        resp=[]
        if self.file is None:
            self.file = self.sock.makefile('rb')
        while 1:
            # There's no real reason to save the result of this call to select().
            # If the select times out, the next call to readline() will return '',
            # which will cause the function to believe that the remote system has
            # disconnected, which is probably best.
            select.select([self.file], [], [], _smtpTimeout)
            line = self.file.readline()
            if line == '':
                self.close()
                raise smtplib.SMTPServerDisconnected("Connection unexpectedly closed")
            if self.debuglevel > 0: print>>stderr, 'reply:', repr(line)
            resp.append(line[4:].strip())
            code=line[:3]
            # Check that the error code is syntactically correct.
            # Don't attempt to read a continuation line if it is broken.
            try:
                errcode = int(code)
            except ValueError:
                errcode = -1
                break
            # Check if multiline response.
            if line[3:4]!="-":
                break

        errmsg = "\n".join(resp)
        if self.debuglevel > 0:
            print>>stderr, 'reply: retcode (%s); Msg: %s' % (errcode,errmsg)
        return errcode, errmsg


if __name__ == '__main__':
    # For debugging, you can create a file that contains just one
    # line, beginning with an 's' character, followed by an email
    # address.  Run this script with the name of that file as an
    # argument, and it'll validate that email address.
    if not sys.argv[1:]:
        print 'Use:  dialback.py <control file>'
        sys.exit(1)
    print doFilter('', sys.argv[1:])
