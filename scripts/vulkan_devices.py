"""Discover experimental Vulkan devices and validate explicit selections."""
import json
import subprocess


def discover(build):
    result = subprocess.run([str(build / 'list_vulkan_devices')], capture_output=True,
                            text=True, check=True, timeout=30)
    devices = json.loads(result.stdout)
    validate_indices(devices)
    return devices


def validate_indices(devices):
    if not isinstance(devices, list):
        raise ValueError('Vulkan devices must be a list')
    if any(type(device) is not int or not 0 <= device < 16 for device in devices):
        raise ValueError('invalid Vulkan device index')
    if len(set(devices)) != len(devices):
        raise ValueError('duplicate Vulkan device index')


def select(available, requested=None):
    validate_indices(available)
    chosen = available if requested is None else requested
    validate_indices(chosen)
    if not chosen:
        raise RuntimeError('no compatible Vulkan devices available')
    if not set(chosen).issubset(available):
        raise ValueError('selected Vulkan device is unavailable')
    return chosen


def identity(build, index):
    validate_indices([index])
    result = subprocess.run([str(build / 'list_vulkan_devices'), '--identity', str(index)],
                            capture_output=True, text=True, check=True, timeout=30)
    device = json.loads(result.stdout)
    if device['index'] != index:
        raise ValueError('Vulkan identity differs from requested index')
    return device
