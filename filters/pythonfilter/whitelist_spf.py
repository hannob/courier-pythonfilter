#!/usr/bin/python
# whitlist_spf -- Courier filter which checks SPF records using the "spf" module
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

import sys
import courier.control
import spf


def init_filter():
    # Record in the system log that this filter was initialized.
    sys.stderr.write('Initialized the whitelist_spf python filter\n')


def do_filter(body_path, control_paths):
    """Use the SPF mechanism to whitelist email."""
    try:
        senders_mta = courier.control.get_senders_mta(control_paths)
        senders_ip = courier.control.get_senders_ip(control_paths)
        sender = courier.control.get_sender(control_paths)
    except:
        return '451 Internal failure locating control files'

    # Don't waste time on DSNs.
    if sender == '':
        return ''

    helo = senders_mta.split(' ')[1]
    (spf_result, spf_explanation) = spf.check2(senders_ip, sender, helo)
    if spf_result == 'pass':
        return '200 Ok'
    return ''


if __name__ == '__main__':
    # Run this script with the name of a properly formatted control
    # file as an argument, and it'll print either "200 Ok" to
    # indicate that the sender is whitelisted, or nothing to
    # indicate that the remaining filters would be run.
    if not sys.argv[1:]:
        print('Use:  whitelist_spf.py <control file>')
        sys.exit(1)
    init_filter()
    print(do_filter('', sys.argv[1:]))
