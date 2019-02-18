#!/usr/bin/python
# add_signature -- Adds standard signatures to AUTH user email.
# Copyright (C) 2008  Enda Cronnolly <enda@codefoundry.com>
# Copyright (C) 2008  Gordon Messmer <gordon@dragonsdawn.net>
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
import email
import email.charset
import email.generator
import email.mime.multipart
import email.mime.text
import courier.control
import courier.xfilter


domains = {'example.com': '/etc/courier/signatures/example.com'}


def get_signature_for_domain(domain):
    if domain in domains:
        sig_file = open(domains[domain])
        return sig_file.read()
    return None


def init_filter():
    courier.config.apply_module_config('add_signature.py', globals())
    # Record in the system log that this filter was initialized.
    sys.stderr.write('Initialized the "add_signature" python filter\n')


def do_filter(body_path, control_paths):
    sender = courier.control.get_auth_user(control_paths, body_path)
    if not sender:
        return ''
    sender_bits = sender.split('@')
    if len(sender_bits) == 1:
        signature = get_signature_for_domain('')
    else:
        signature = get_signature_for_domain(sender_bits[1])
    if not signature:
        return ''
    # Set the preferred encoding for UTF-8, which will be used in the signature
    email.charset.add_charset('utf-8', email.charset.SHORTEST, email.charset.QP, None)
    # Load the message from the body_path
    mfilter = courier.xfilter.XFilter('add_signature',
                                      body_path, control_paths)
    original = mfilter.getMessage()
    # Create a new message object
    msg = email.mime.multipart.MIMEMultipart('mixed')
    # Attach the original message and the signature.
    msg.attach(original)
    msg.attach(email.mime.text.MIMEText(signature, _charset='utf-8'))
    # Move the headers from the original message to the new message.
    for x in original.items():
        # Dont' move the following MIME related headers.
        if x[0] in ('Content-Type', 'Content-Transfer-Encoding',
                    'Content-Disposition', 'Content-Description',
                    'MIME-Version'):
            continue
        msg.add_header(x[0], x[1])
        del original[x[0]]
    # Replace the message body
    mfilter.setMessage(msg)
    # Return the value from submit(), which may stop other filters
    # from running.
    return mfilter.submit()
