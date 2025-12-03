from types import SimpleNamespace


class TuyaRemoteDeviceKey(SimpleNamespace):
    key: str
    key_id: int
    key_name: str
    standard_key: bool

    def __init__(
        self, key: str, key_id: int, key_name: str, standard_key: bool
    ) -> None:
        self.key = key
        self.key_id = key_id
        self.key_name = key_name
        self.standard_key = standard_key


class TuyaRemoteDevice(SimpleNamespace):
    remote_name = str
    category_id = str
    brand_id = str
    remote_index = str
    remote_id = str
    keys: list

    def __init__(self, props: dict, keys: list) -> None:
        self.map(props)
        self.keys = keys

    def map(self, props: dict):
        self.remote_name = props["remote_name"]
        self.category_id = props["category_id"]
        self.brand_id = props["brand_id"]
        self.remote_index = props["remote_index"]
        self.remote_id = props["remote_id"]


class TuyaRemote(SimpleNamespace):
    remote_id: str
    remote_devices = list

    def __init__(self, remote_id: str, remote_devices: list) -> None:
        self.remote_id = remote_id
        self.remote_devices = remote_devices
