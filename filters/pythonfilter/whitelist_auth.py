#!/usr/bin/python
# whitelist_auth -- Courier filter which exempts authenticated users from filtering
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
import courier.control


def init_filter():
    # Record in the system log that this filter was initialized.
    sys.stderr.write('Initialized the "whitelist_auth" python filter\n')


def do_filter(body_path, control_paths):
    """Return a 200 code if the sender appears to have authenticated.

    Courier does not currently contain this information in its control
    files, so we look at the first Received header.  The first one
    should always have come from Courier, and be trusted information.

    After returning a 200 code, the pythonfilter process will
    discontinue further filter processing.

    """

    auth_user = courier.control.get_auth_user(control_paths, body_path)
    if auth_user:
        return '200 Ok'
    # Return no decision for everyone else.
    return ''


if __name__ == '__main__':
    # For debugging, you can create a file that contains a message,
    # including the headers.
    # Run this script with the name of that file as an argument,
    # and it'll print either "200 Ok" to indicate that the sender
    # is whitelisted, or nothing to indicate that the remaining
    # filters would be run.
    if not sys.argv[1:]:
        print('Use:  whitelist_auth.py <control file>')
        sys.exit(1)
    init_filter()
    print(do_filter(sys.argv[1], []))
