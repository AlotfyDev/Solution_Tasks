from __future__ import annotations

import socket
from unittest.mock import patch

import pytest

from task_cli.utils.port import find_free_port, scan_available_ports


class TestFindFreePort:
    def test_without_args_returns_ephemeral_port(self):
        port = find_free_port()
        assert isinstance(port, int)
        assert 1024 <= port <= 65535

    def test_with_preferred_range(self):
        port = find_free_port(preferred_range=(9000, 9999))
        assert isinstance(port, int)
        assert 9000 <= port <= 9999

    def test_range_fully_occupied_raises_runtime_error(self):
        with patch("task_cli.utils.port.socket.socket") as mock_socket:
            mock_instance = mock_socket.return_value.__enter__.return_value
            mock_instance.connect_ex.return_value = 0
            with pytest.raises(RuntimeError, match="No available port in range"):
                find_free_port(preferred_range=(9000, 9000), limit=1)

    def test_port_is_reusable_after_find(self):
        port = find_free_port()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", port))
            s.close()


class TestScanAvailablePorts:
    def test_returns_list_of_ints(self):
        ports = scan_available_ports(limit=3)
        assert isinstance(ports, list)
        assert all(isinstance(p, int) for p in ports)

    def test_respects_limit(self):
        ports = scan_available_ports(limit=2)
        assert len(ports) <= 2

    def test_custom_range(self):
        ports = scan_available_ports(start_port=9000, end_port=9999, limit=2)
        if ports:
            assert 9000 <= ports[0] <= 9999

    def test_fully_occupied_returns_empty(self):
        with patch("task_cli.utils.port.socket.socket") as mock_socket:
            mock_instance = mock_socket.return_value.__enter__.return_value
            mock_instance.connect_ex.return_value = 0
            result = scan_available_ports(8000, 8005, limit=10)
            assert result == []
