"""F5 BIG-IP Device Module."""
from rancid_ng.core.device import DeviceModule
from rancid_ng.devices import register_device

@register_device
class F5BigIP(DeviceModule):
    name = "bigip"
    aliases = ["bigip13"]
    login_script = "clogin"

    def init(self):
        self.process_history.add("", "", "", f"!RANCID-CONTENT-TYPE: {self.devtype}\n!\n")
        return 0

    def inloop(self, session):
        for cmd, _ in self.command_table:
            if cmd in self._commands_run:
                continue
            output = session.run_command(cmd) if session else ""
            if output:
                for line in output.splitlines():
                    self.process_history.add("", "", "", line + "\n")
            self._commands_run.add(cmd)
        self.clean_run = True
        return 0
