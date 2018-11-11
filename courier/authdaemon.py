# courier.authdaemon -- python module for Courier's authdaemon
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

import errno
import select
import socket
import courier.config


socket_path = '/var/spool/authdaemon/socket'
TIMEOUT_SOCK = 10
TIMEOUT_WRITE = 10
TIMEOUT_READ = 30


def _setup():
    courier.config.apply_module_config('authdaemon.py', globals())


def _connect():
    try:
        auth_sock = socket.socket(socket.AF_UNIX)
    except socket.error:
        raise IOError('could not create socket')
    if TIMEOUT_SOCK == 0:
        try:
            auth_sock.connect(socket_path)
            auth_sock.setblocking(0)
        except socket.error:
            raise IOError('could not connect to authdaemon socket')
    else:
        # Try to connect to the non-blocking socket.  We expect connect()
        # to throw an error, indicating that the connection is in progress.
        # Use select to wait for the connection to complete, and then check
        # for errors with getsockopt.
        auth_sock.setblocking(0)
        try:
            auth_sock.connect(socket_path)
        except socket.error as e:
            if e.errno != errno.EINPROGRESS:
                raise IOError('connection failed, error: %d, "%s"' % (e.errno, e.strerror))
            ready_socks = select.select([auth_sock], [], [], TIMEOUT_SOCK)
            if auth_sock in ready_socks[0]:
                so_error = auth_sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
                if so_error:
                    raise IOError('connection failed, error: %d' % so_error)
            else:
                # The connection timed out.
                raise IOError('connection timed out')
    return auth_sock


def _write_auth(auth_sock, cmd):
    try:
        # Loop: Wait for select() to indicate that the socket is ready
        # for data, and call send().  If send returns a value smaller
        # than the total length of cmd, save the remaining data, and
        # continue to attempt to send it.  If select() times out, raise
        # an exception and let the handler close the connection.
        while cmd:
            ready_socks = select.select([], [auth_sock], [], TIMEOUT_WRITE)
            if not ready_socks[1]:
                raise socket.error('Write timed out.')
            sent = auth_sock.send(cmd)
            if sent < len(cmd):
                cmd = cmd[sent:]
            else:
                # All the data was written, break the loop.
                break
    except socket.error:
        raise IOError('connection to authdaemon lost while sending request')


def _read_auth(auth_sock, term):
    data = ''
    datal = 0
    terml = len(term)
    while 1:
        ready_socks = select.select([auth_sock], [], [], TIMEOUT_READ)
        if not ready_socks[0]:
            raise IOError('timeout when reading authdaemon reply')
        buf = auth_sock.recv(1024)
        if not buf:
            raise IOError('connection closed when reading authdaemon reply')
        data += buf
        datal += len(buf)
        # Detect the termination marker from authdaemon
        if datal >= terml and data.endswith(term):
            break
        if datal >= 5 and data.endswith('FAIL\n'):
            break
    return data.split('\n')


def _do_auth(cmd):
    """Send cmd to the authdaemon, and return a dictionary containing its reply."""
    auth_sock = _connect()
    _write_auth(auth_sock, cmd)
    auth_data = _read_auth(auth_sock, '\n.\n')
    auth_info = {}
    for auth_line in auth_data:
        if auth_line == 'FAIL':
            # Return None, discarding all other data from authdaemon
            return None
        if '=' not in auth_line:
            continue
        (auth_key, auth_val) = auth_line.split('=', 1)
        auth_info[auth_key] = auth_val
    return auth_info


def get_user_info(service, uid):
    cmd = 'PRE . %s %s\n' % (service, uid)
    user_info = _do_auth(cmd)
    return user_info


# Call _setup to correct the socket path
_setup()

# Deprecated names preserved for compatibility with older releases
getUserInfo = get_user_info
