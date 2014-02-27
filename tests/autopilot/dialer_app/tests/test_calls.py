# -*- Mode: Python; coding: utf-8; indent-tabs-mode: nil; tab-width: 4 -*-
# Copyright 2013 Canonical
# Author: Martin Pitt <martin.pitt@ubuntu.com>
#
# This file is part of dialer-app.
#
# dialer-app is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 3, as published
# by the Free Software Foundation.

"""Tests for the Dialer App using ofono-phonesim"""

from __future__ import absolute_import

import subprocess
import os
import time

from autopilot.matchers import Eventually
from testtools.matchers import Equals, NotEquals, MismatchError
from testtools import skipIf, skipUnless

from dialer_app.tests import DialerAppTestCase
from dialer_app import helpers


@skipUnless(helpers.is_phonesim_running(),
            "this test needs to run under with-ofono-phonesim")
@skipIf(os.uname()[2].endswith("maguro"),
        "tests cause Unity crashes on maguro")
class TestCalls(DialerAppTestCase):
    """Tests for simulated phone calls."""

    def setUp(self):
        # provide clean history
        self.history = os.path.expanduser(
            "~/.local/share/history-service/history.sqlite")
        if os.path.exists(self.history):
            subprocess.call(["pkill", "history-daemon"])
            os.rename(self.history, self.history + ".orig")

        super(TestCalls, self).setUp()

        # should have an empty history at the beginning of each test
        self.history_list = self.app.select_single(objectName="historyList")
        self.assertThat(self.history_list.visible, Equals(False))
        self.assertThat(self.history_list.count, Equals(0))

    def tearDown(self):
        super(TestCalls, self).tearDown()

        # ensure that there are no leftover calls in case of failed tests
        subprocess.call(["/usr/share/ofono/scripts/hangup-all"])

        # restore history
        if os.path.exists(self.history + ".orig"):
            subprocess.call(["pkill", "history-daemon"])
            os.rename(self.history + ".orig", self.history)

    def test_outgoing_noanswer(self):
        """Outgoing call to a normal number, no answer"""
        number = "144"
        self.main_view.dialer_page.call_number(number)
        self.assertThat(
            self.main_view.live_call_page.title, Eventually(Equals(number)))

        self.main_view.live_call_page.click_hangup_button()

        # log should show call to "Unknown"
        self.assertThat(self.history_list.count, Eventually(Equals(1)))
        self.assertThat(self.history_list.select_single(
            "Label", text="Unknown"), NotEquals(None))

    def test_outgoing_answer_local_hangup(self):
        """Outgoing call, remote answers, local hangs up"""
        # 06123xx causes accept after xx seconds
        number = "0612302"

        self.main_view.dialer_page.call_number(number)
        self.assertThat(
            self.main_view.live_call_page.title, Eventually(Equals(number)))

        # stop watch should start counting
        elapsed_time = self.main_view.live_call_page.get_elapsed_call_time()
        self.assertIn("00:0", elapsed_time)

        # should still be connected after some time
        time.sleep(3)
        self.assertIn("00:0", elapsed_time)
        self.main_view.live_call_page.click_hangup_button()

    def test_outgoing_answer_remote_hangup(self):
        """Outgoing call, remote answers and hangs up"""
        number = "0512303"

        # 05123xx causes immediate accept and hangup after xx seconds
        self.main_view.dialer_page.call_number(number)
        self.assertThat(
            self.main_view.live_call_page.title, Eventually(Equals(number)))

        # stop watch should start counting
        elapsed_time = self.main_view.live_call_page.get_elapsed_call_time()
        self.assertIn("00:0", elapsed_time)

        # after remote hangs up, should switch to call log page and show call
        # to "Unknown"
        self.assertThat(self.history_list.visible, Eventually(Equals(True)))
        self.assertThat(self.history_list.count, Eventually(Equals(1)))
        self.assertThat(self.history_list.select_single(
            "Label", text="Unknown"), NotEquals(None))

    def test_incoming(self):
        """Incoming call"""
        number = "1234567"
        helpers.invoke_incoming_call()

        # wait for incoming call, accept; it would be nicer to fake-click the
        # popup notification, but as this isn't generated by dialer-app it
        # isn't exposed to autopilot
        helpers.wait_for_incoming_call()
        time.sleep(1)  # let's hear the ringing sound for a second :-)
        subprocess.check_call(
            [
                "dbus-send", "--session", "--print-reply",
                "--dest=com.canonical.Approver", "/com/canonical/Approver",
                "com.canonical.TelephonyServiceApprover.AcceptCall"
            ], stdout=subprocess.PIPE)

        # call back is from that number
        self.assertThat(
            self.main_view.live_call_page.title, Eventually(Equals(number)))

        # stop watch should start counting
        elapsed_time = self.main_view.live_call_page.get_elapsed_call_time()
        self.assertIn("00:0", elapsed_time)

        try:
            self.main_view.live_call_page.click_hangup_button()
        except MismatchError as e:
            print('Expected failure due to known Mir crash '
                  '(https://launchpad.net/bugs/1240400): %s' % e)
