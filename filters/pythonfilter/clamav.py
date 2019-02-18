#!/usr/bin/python
# clamav -- Courier filter which scans messages with ClamAV
# Copyright (C) 2004-2008  Robert Penz <robert@penz.name>
# Copyright (C) 2004-2008  Gordon Messmer <gordon@dragonsdawn.net>
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

import sys
import courier.config
import courier.quarantine
import pyclamd

local_socket = ''
action = 'reject'


def scan_message(body_path, control_paths):
    try:
        clamd = pyclamd.ClamdUnixSocket(local_socket)
        avresult = clamd.scan_file(body_path)
    except pyclamd.ConnectionError as e:
        return "430 Virus scanner error: " + str(e)
    if avresult is not None and body_path in avresult:
        if avresult[body_path][0] == 'FOUND':
            return handle_virus(body_path, control_paths, avresult[body_path][1])
        return "430 Virus scanner error: " + avresult[body_path][1]
    return ''


def handle_virus(body_path, control_paths, virus_signature):
    if action == 'reject':
        return "554 Virus found - Signature is %s" % virus_signature
    courier.quarantine.quarantine(body_path, control_paths,
                                  'The virus %s was found in the message' % virus_signature)
    return '050 OK'


def init_filter():
    courier.config.apply_module_config('clamav.py', globals())
    courier.quarantine.init()
    # Record in the system log that this filter was initialized.
    sys.stderr.write('Initialized the "clamav" python filter\n')


def do_filter(body_path, control_paths):
    return scan_message(body_path, control_paths)


if __name__ == '__main__':
    # we only work with 1 parameter
    if len(sys.argv) < 3:
        print("Usage: clamav.py <message_body_path> <control_paths>")
        sys.exit(0)
    init_filter()
    print(do_filter(sys.argv[1], sys.argv[2:]))
