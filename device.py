from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

class DeviceType(str, Enum):
    CAMERA = "CAMERA"

@dataclass
class Device:
    name: str
    device_type: DeviceType
    online: bool
    last_contact: datetime = field(default_factory=datetime.now)
    def __str__(self) -> str:
        status = "ONLINE" if self.online else "OFFLINE"
        last_seen = self.last_contact.strftime("%m-%d %l:%M")
        return f"{self.name} | {self.device_type.value} | {status} | Last contact: {last_seen}"