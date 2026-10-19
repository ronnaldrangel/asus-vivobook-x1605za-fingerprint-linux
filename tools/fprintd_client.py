"""Cliente mínimo del bus de sistema para fprintd."""

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402


BUS_NAME = "net.reactivated.Fprint"
OBJECT_PATH = "/net/reactivated/Fprint/Device/0"
INTERFACE = "net.reactivated.Fprint.Device"


class FprintdError(Exception):
    pass


class FprintdDevice:
    def __init__(self):
        self.bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        self.proxy = Gio.DBusProxy.new_sync(
            self.bus,
            Gio.DBusProxyFlags.NONE,
            None,
            BUS_NAME,
            OBJECT_PATH,
            INTERFACE,
            None,
        )
        self._signal_id = None

    def _call(self, method, params=None, timeout=30000):
        try:
            return self.proxy.call_sync(
                method,
                params,
                Gio.DBusCallFlags.NONE,
                timeout,
                None,
            )
        except GLib.Error as error:
            raise FprintdError(error.message) from error

    def claim(self):
        self._call("Claim", GLib.Variant("(s)", ("",)))

    def release(self):
        self._call("Release")

    def enrolled_fingers(self):
        try:
            result = self._call(
                "ListEnrolledFingers",
                GLib.Variant("(s)", ("",)),
            )
        except FprintdError as error:
            if "NoEnrolledPrints" in str(error):
                return []
            raise
        return list(result.unpack()[0])

    def delete_finger(self, finger):
        self._call(
            "DeleteEnrolledFinger",
            GLib.Variant("(s)", (finger,)),
        )

    def enroll_start(self, finger):
        self._call("EnrollStart", GLib.Variant("(s)", (finger,)))

    def enroll_stop(self):
        self._call("EnrollStop")

    def verify_start(self, finger):
        self._call("VerifyStart", GLib.Variant("(s)", (finger,)))

    def verify_stop(self):
        self._call("VerifyStop")

    def on_signal(self, name, callback):
        def dispatch(_proxy, _sender, signal_name, params):
            if signal_name == name:
                callback(*params.unpack())

        self._signal_id = self.proxy.connect("g-signal", dispatch)
        return self._signal_id

    def close(self):
        if self._signal_id is not None:
            try:
                self.proxy.disconnect(self._signal_id)
            finally:
                self._signal_id = None
