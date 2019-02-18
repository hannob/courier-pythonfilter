#!/usr/bin/python
# quota -- Courier filter which checks recipients' quotas
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

import os
import sys
import courier.authdaemon
import courier.config
import courier.control


def parse_quota(quota):
    size = 0
    messages = 0
    qbits = [x.strip() for x in quota.split(',')]
    for qbit in qbits:
        if qbit[-1] == 'S':
            size = int(qbit[:-1])
        elif qbit[-1] == 'C':
            messages = int(qbit[:-1])
        else:
            raise ValueError('quota string "%s" not parseable' % quota)
    return (size, messages)


def check_quota(addr):
    user_info = courier.authdaemon.get_user_info('smtp', addr)
    if user_info is None:
        # shouldn't happen if addr is local or hosted, and
        # courier accepted the address
        sys.stderr.write('quota filter: authdaemon failed to look up "%s"\n' % addr)
        return ''
    if 'MAILDIR' in user_info:
        maildirsize = os.path.join(user_info['MAILDIR'], 'maildirsize')
    else:
        maildirsize = os.path.join(user_info['HOME'], 'Maildir', 'maildirsize')
    try:
        size_file = open(maildirsize, 'r')
        (quota_size, quota_count) = parse_quota(size_file.readline())
        mail_size = 0
        mail_count = 0
        quota_line = size_file.readline()
        while quota_line:
            (line_size, line_count) = quota_line.strip().split()
            mail_size += int(line_size)
            mail_count += int(line_count)
            quota_line = size_file.readline()
        if ((quota_size and mail_size >= quota_size)
                or (quota_count and mail_count >= quota_count)):
            return 'User "%s" is over quota' % addr
    except:
        return ''
    return ''


def init_filter():
    # Record in the system log that this filter was initialized.
    sys.stderr.write('Initialized the "quota" python filter\n')


def do_filter(body_path, control_paths):
    """Reject mail if any recipient is over quota"""
    rcpts = courier.control.get_recipients_data(control_paths)
    for x in rcpts:
        (user, domain) = x[0].split('@', 1)
        if courier.config.is_local(domain):
            quota_error = check_quota(user)
            if quota_error:
                return '421 %s' % quota_error
        elif courier.config.is_hosteddomain(domain):
            quota_error = check_quota(x[0])
            if quota_error:
                return '421 %s' % quota_error
    return ''


if __name__ == '__main__':
    # For debugging, you can create a file or set of files that
    # mimics the Courier control file set.
    # Run this script with the name of those files as arguments,
    # and it'll check each recipient's quota.
    if not sys.argv[1:]:
        print('Use:  quota.py <control file>')
        sys.exit(1)
    init_filter()
    print(do_filter('', sys.argv[1:]))
