#!/usr/bin/python
# noreceivedheaders -- Courier filter which strips AUTH data from messages
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
import courier.xfilter


def init_filter():
    # Record in the system log that this filter was initialized.
    sys.stderr.write('Initialized the "noreceivedheaders" python filter\n')


def do_filter(body_path, control_paths):
    """Remove the Received header if the sender authenticated himself."""
    auth_user = courier.control.get_auth_user(control_paths, body_path)
    if auth_user is None:
        return ''
    mfilter = courier.xfilter.XFilter('noreceivedheaders', body_path,
                                      control_paths)
    mmsg = mfilter.getMessage()
    del mmsg['Received']
    submit_val = mfilter.submit()
    return submit_val


if __name__ == '__main__':
    # For debugging, you can create a file that contains a message,
    # including the headers.
    if not sys.argv[1:]:
        print('Use:  noreceivedheaders.py <control file>')
        sys.exit(1)
    init_filter()
    courier.xfilter.XFilter = courier.xfilter.DummyXFilter
    print(do_filter(sys.argv[1], []))
