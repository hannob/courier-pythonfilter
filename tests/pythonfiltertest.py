#!/usr/bin/python3
# pythonfilter -- A python framework for Courier global filters
# Copyright (C) 2003-2018  Gordon Messmer <gordon@dragonsdawn.net>
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
import select
import socket
import sys

# Add the cwd to PATH so that a modified courier-config is used
# by the courier.config module.
os.environ['PATH'] = '%s:%s' % (os.getcwd(), os.environ['PATH'])
# Add the local library path to PYTHONPATH so that the child
# process (pythonfilter) loads modules from this dir rather than
# the system library path.
if 'PYTHONPATH' in os.environ:
    os.environ['PYTHONPATH'] = '%s/..:%s' % (os.getcwd(), os.environ['PYTHONPATH'])
else:
    os.environ['PYTHONPATH'] = '%s/..' % (os.getcwd(),)

# File descriptor 3 is reserved while creating pipes.
fd3 = open('/dev/null')
# pythonfilter will close one end of this pipe to signal that it
# is listening and ready to process messages.
ready_fd = os.pipe()
# This process will close one end of this pipe to signal that
# pythonfilter should shut down.
term_fd = os.pipe()
fd3.close()

child_pid = os.fork()
if child_pid == 0:
    # The child process will dup its own end of each pipe to the
    # fd where it will be expected by pythonfilter and then close
    # the original reference.
    os.dup2(term_fd[0], 0)
    os.dup2(ready_fd[1], 3)
    os.close(term_fd[0])
    os.close(ready_fd[1])
    # Close the parent's end of the pipe.
    os.close(term_fd[1])
    os.close(ready_fd[0])
    os.execlp('python3', 'python3', '../pythonfilter')
else:
    # The test process will close the child's end of each pipe and
    # wait for pythonfilter to close its end of the "ready" pipe.
    os.close(term_fd[0])
    os.close(ready_fd[1])
    ready_files = select.select([ready_fd[0]], [], [])
    if ready_fd[0] not in ready_files[0]:
        print('Error: notification file not closed')
        sys.exit(0)

socket_path = '%s/spool/courier/allfilters/pythonfilter' % os.getcwd()
sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
sock.connect(socket_path)
sock.sendall(('%s/queuefiles/data-test1\n' % os.getcwd()).encode())
sock.sendall(('%s/queuefiles/control-duplicate\n' % os.getcwd()).encode())
sock.sendall(('\n').encode())

status = sock.recv(1024).decode()
print('Status: %s' % status)

# Tell pythonfilter to shut down.
os.close(term_fd[1])

# Use non-zeo exit if we did not get the expected response from
# pythonfilter
if status != '200 Ok':
    sys.exit(1)
