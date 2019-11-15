#
#  Copyright (C) 2018
#            Smithsonian Astrophysical Observatory
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License along
#  with this program; if not, write to the Free Software Foundation, Inc.,
#  51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

"""
Support downloading data from URLs in CIAO.

CIAO 4.11 does not include any SSL support, instead relying on the OS.
This can cause problems on certain platforms. So try with Python and
then fall through to curl or wget.

This is an internal module, and so the API it provides is not
considered stable (e.g. we may remove this module at any time). Use
at your own risk.

"""


from io import BytesIO
from subprocess import check_output
import urllib
import urllib.request
import urllib.error

import ciao_contrib.logger_wrapper as lw

logger = lw.initialize_module_logger("downloadutils")

v3 = logger.verbose3
v4 = logger.verbose4


def manual_download(url):
    """Try curl then wget to query the URL.

    Parameters
    ----------
    url : str
        The URL for the query; see construct_query

    Returns
    -------
    ans : StringIO instance
        The response

    """

    v3("Fall back to curl or wget to download: {}".format(url))

    # Should package this up nicely, but hardcode for the moment.
    #
    # It is not clear if this is sufficient to catch "no curl"
    # while allowing errors like "no access to the internet"
    # to not cause too much pointless work.
    #
    args = ['curl', '--silent', '-L', url]
    v4("About to execute: {}".format(args))

    try:
        rsp = check_output(args)

    except FileNotFoundError as exc1:
        v3("Unable to call curl: {}".format(exc1))
        args = ['wget', '--quiet', '-O-', url]
        v4("About to execute: {}".format(args))

        try:
            rsp = check_output(args)

        except FileNotFoundError as exc2:
            v3("Unable to call wget: {}".format(exc2))
            emsg = "Unable to access the URL {}.\n".format(url) + \
                   "Please install curl or wget (and if you " + \
                   "continue to see this message, contact the " + \
                   "CXC HelpDesk)."
            raise RuntimeError(emsg)

    return BytesIO(rsp)


def retrieve_url(url, timeout=None):
    """Handle possible problems retrieving the URL contents.

    Using URLs with the https scheme causes problems for certain OS
    set ups because CIAO 4.11 does not provide SSL support, but relies
    on the system libraries to work. This is "supported" by falling
    over from Python to external tools (curl or wget).

    Parameters
    ----------
    url : str
        The URL to retrieve.
    timeout : optional
        The timeout parameter for the urlopen call; if not
        None then the value is in seconds.

    Returns
    -------
    response : StringIO instance
        The response

    """

    try:
        v3("Retrieving URL: {} timeout={}".format(url, timeout))
        if timeout is None:
            return urllib.request.urlopen(url)
        else:
            return urllib.request.urlopen(url, timeout=timeout)

    except urllib.error.URLError as ue:
        v3("Error opening URL: {}".format(ue))
        v3("error.reason = {}".format(ue.reason))

        # Assume this is the error message indicating "no SSL support"
        # There is a new (in CIAO 4.11) message
        # "urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed (_ssl.c:719)"
        #
        # It appears that the reason attribute can be an object, so
        # for now explicitly convert to a string:
        reason = str(ue.reason)
        if reason.find('unknown url type: https') != -1 or \
           reason.find('CERTIFICATE_VERIFY_FAILED') != -1:
            return manual_download(url)

        # There used to be a check on the reason for the error,
        # converting it into a "user-friendly" message, but this
        # was error prone (the check itself was faulty) and
        # potentially hid useful error information. So just
        # re-raise the error here after logging it.
        #
        raise