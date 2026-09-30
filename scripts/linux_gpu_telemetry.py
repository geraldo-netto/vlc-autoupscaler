"""Linux read-only telemetry adapter, bound to Vulkan's PCI identity."""
from pathlib import Path
import re


def resolve_device(identity, requested=None, drm_root=Path('/sys/class/drm')):
    pci = identity.get('pci')
    if not isinstance(pci, str) or not re.fullmatch(r'[0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-7]', pci):
        raise RuntimeError('GPU telemetry unavailable: Vulkan has no supported PCI identity')
    candidates = [requested] if requested is not None else sorted(drm_root.glob('card[0-9]*/device'))
    matches = {path.resolve() for path in candidates if path.resolve().name == pci}
    if len(matches) != 1:
        raise ValueError('telemetry device does not match selected Vulkan PCI identity')
    device = matches.pop()
    for field in ('vendor', 'device'):
        if int((device / field).read_text().strip(), 16) != identity[field + '_id']:
            raise ValueError('sysfs identity does not match selected Vulkan device')
    return device


def sensor_paths(device):
    hwmon = next(iter(sorted((device / 'hwmon').glob('hwmon*'))), None)
    fields = dict(clock_hz='freq1_input', memory_hz='freq2_input',
                  power_uw='power1_average', temperature_mc='temp1_input')
    return dict({name: hwmon / filename if hwmon else None for name, filename in fields.items()},
                busy_percent=device / 'gpu_busy_percent')


def sensor_value(path):
    if path is None:
        return 'unavailable: hwmon sensor not exposed'
    try:
        return int(path.read_text())
    except (OSError, ValueError) as error:
        return 'unavailable: ' + str(error)


def power_policy(device):
    try:
        return dict(available=True, value=(device / 'power_dpm_force_performance_level').read_text())
    except OSError as error:
        return dict(available=False, reason=str(error))
