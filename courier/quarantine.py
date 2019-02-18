# courier.quarantine -- python module for quarantining and releasing messages
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

import dbm
import datetime
import email
import fcntl
import os
import time
import pickle
import courier.config
import courier.control
import courier.sendmail
import courier.xfilter


# Defaults:
config = {'siteid': 'local',
          'dir': '/var/lib/pythonfilter/quarantine',
          'days': 14,
          'default': 1}


def init():
    global config
    # Load the configuration if it has not already been loaded.
    if 'default' in config:
        config = courier.config.get_module_config('quarantine')


def _get_db():
    """Return the dbm and lock file handles."""
    dbmfile = '%s/msgs.db' % config['dir']
    lockfile = '%s/msgs.lock' % config['dir']
    lock = open(lockfile, 'w')
    fcntl.flock(lock, fcntl.LOCK_EX)
    dbm_stream = dbm.open(dbmfile, 'c')
    return(dbm_stream, lock)


def _close_db(dbm_stream, lock):
    """Unlock and close the lock and dbm files"""
    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    lock.close()
    dbm_stream.close()


def _copy_file(source, destination):
    dfile = open(destination, 'w')
    sfile = open(source, 'r')
    dfile.write(sfile.read())


def send_notice(message, address, sender=None):
    if not sender:
        sender = 'postmaster@%s' % courier.config.me()
    msg = ('From: Mail Quarantine System <%s>\r\n'
           'To: <%s>\r\n'
           'Subject: Quarantine notice\r\n\r\n'
           '%s'
           % (sender, address, message))
    # Send the recipient a notice if notify_recipient isn't
    # available, or if it is present and a true value.
    rcpts = []
    if('notify_recipient' not in config
       or config['notify_recipient']):
        rcpts.append(address)
    if 'also_notify' in config and config['also_notify']:
        rcpts.append(config['also_notifiy'])
    if rcpts:
        courier.sendmail.sendmail('', rcpts, msg)


def send_failure_notice(requested_id, address):
    message = """The quarantine system received a request from your address
to release the message with id '%s' from the quarantine.  That message
was not found.  It may have already expired.

I'm sorry that it didn't work out.  Please contact your system admin
for further assistance.
""" % requested_id
    send_notice(message, address)


def quarantine(body_file, control_files, explanation):
    # Generate an ID for this quarantined message.  The ID will consist
    # of the inode number for the body file.  The inode number from the
    # original body file will be used for the temporary file's name.
    obodyinfo = os.stat(body_file)
    bodypath = '%s/tmp.%s' % (config['dir'], obodyinfo.st_ino)
    body = open(bodypath, 'w')
    bodyinfo = os.fstat(body.fileno())
    body.close()
    msgid = bodyinfo.st_ino
    # Copy files to quarantine
    quarantine_paths = ('%s/D%s' % (config['dir'], msgid), [])
    os.rename(bodypath, quarantine_paths[0])
    ctl_file_ext = ''
    ctl_file_num = 0
    _copy_file(body_file, quarantine_paths[0])
    for x in control_files:
        ctl_file_path = '%s/C%s%s' % (config['dir'], msgid, ctl_file_ext)
        ctl_file_num += 1
        ctl_file_ext = '.%s' % ctl_file_num
        _copy_file(x, ctl_file_path)
        quarantine_paths[1].append(ctl_file_path)
    # Open and lock the quarantine DB
    (dbm_stream, lock) = _get_db()
    # Record this set of files in the DB
    dbm_stream['%d' % msgid] = pickle.dumps((time.time(), quarantine_paths))
    # Unlock the DB
    _close_db(dbm_stream, lock)
    # Prepare notice for recipients of quarantined message
    # Some sites would prefer that only admins release messages from the
    # quarantine.
    if('user_release' in config
       and config['user_release'] == 0
       and 'also_notify' in config
       and config['also_notify']):
        release_addr = config['also_notify']
    else:
        release_addr = 'quarantine-%s-%s@%s' % (config['siteid'],
                                                msgid,
                                                courier.config.me())
    days = config['days']
    expiration = datetime.date.fromtimestamp(time.time() + (days * 86400)).strftime('%a %B %d, %Y')
    # Parse the message for its sender and subject:
    try:
        bf_stream = open(body_file)
    except:
        raise #InitError('Internal failure opening message data file')
    try:
        qmessage = email.message_from_file(bf_stream)
    except Exception as e:
        # TODO: Handle this error.
        raise #InitError('Internal failure parsing message data file: %s' % str(e))
    qmessage_sender = qmessage['from']
    qmessage_subject = qmessage['subject']
    message = """You received a message that was quarantined because:
%s

This message will be held in the quarantine until %s.
After that time, it will no longer be possible to release the message.

The message appears to have come from %s, although
this address could have been forged and should not be trusted.  The
message subject was "%s".

If this was a message that you were expecting, and you know that it
is safe to continue, then forward this message to the following address
to release the quarantined message.  If you do not recognise the
sender, or were not expecting this message, then releasing it from
the quarantine could be very harmful.  You will almost always want
to simply ignore this notice.

Quarantine release address:
%s
    """ % (explanation,
           expiration,
           qmessage_sender,
           qmessage_subject,
           release_addr)
    # Mark recipients complete and send notices.
    control_data = courier.control.get_control_data(control_files)
    for x in control_data['r']:
        courier.control.del_recipient_data(control_files, x)
        send_notice(message, x[0])


def release(requested_id, address):
    # Open and lock the quarantine DB
    (dbm_stream, lock) = _get_db()
    if requested_id in dbm_stream:
        quarantine_paths = pickle.loads(dbm_stream[requested_id])[1]
    else:
        quarantine_paths = None
    # Unlock the DB
    _close_db(dbm_stream, lock)
    # If quarantine_paths is None, then an invalid ID was requested.
    if not quarantine_paths:
        # Alert the user that his request failed
        send_failure_notice(requested_id, address)
        return
    for x in courier.control.get_control_data(quarantine_paths[1])['r']:
        if(x[0] == address or
           x[1] == address or
           x[1] == '%s%s' % ('rfc822;', address)):
            courier.sendmail.sendmail('', address, quarantine_paths[0].read())
            return
    # If no address matched, alert the user that the request was invalid.
    send_failure_notice(requested_id, address)


def purge():
    # Open and lock the quarantine DB
    (dbm_stream, lock) = _get_db()
    min_time = time.time() - (int(config['days']) * 86400)
    for x in dbm_stream.keys():
        (qtime, quarantine_paths) = pickle.loads(dbm_stream[x])
        if qtime < min_time:
            # Files may have been removed for some reason, don't treat
            # that as a fatal condition.
            try:
                os.remove(quarantine_paths[0])
            except OSError:
                pass
            for p in quarantine_paths[1]:
                try:
                    os.remove(p)
                except OSError:
                    pass
            del dbm_stream[x]
    # Unlock the DB
    _close_db(dbm_stream, lock)

# Deprecated names preserved for compatibility with older releases
sendNotice = send_notice
sendFailureNotice = send_failure_notice
