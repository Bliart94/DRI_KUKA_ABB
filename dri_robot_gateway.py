#!/usr/bin/env python3
import argparse
import json
import re
import socket
import threading
import time
from dataclasses import dataclass
from typing import Optional


COMPACT_RE = re.compile(r"^(?P<status>[0-9]);(?P<cell>[0-9]{2});(?P<part>[0-9]{2});(?P<confidence>[0-9]{3})$")
BOARD_RE = re.compile(r"^B;(?P<mask>[01X]+);(?P<count>[0-9]{2});(?P<unknown>[0-9]{2})$")


@dataclass
class DRITarget:
    status: int
    cell: int
    part: int
    confidence: int

    @classmethod
    def from_compact(cls, message: str) -> "DRITarget":
        message = message.strip()
        m = COMPACT_RE.match(message)
        if not m:
            raise ValueError(f"Invalid DRI compact target message: {message!r}")
        return cls(
            status=int(m.group("status")),
            cell=int(m.group("cell")),
            part=int(m.group("part")),
            confidence=int(m.group("confidence")),
        )

    def to_abb(self) -> str:
        return f"{self.status:d};{self.cell:02d};{self.part:02d};{self.confidence:03d}"

    def to_kuka_line(self) -> str:
        return f"DRI,{self.status:d},{self.cell:d},{self.part:d},{self.confidence:d}"

    def to_kuka_xml(self) -> str:
        return (
            "<DRI>"
            f"<Status>{self.status:d}</Status>"
            f"<Cell>{self.cell:d}</Cell>"
            f"<Part>{self.part:d}</Part>"
            f"<Confidence>{self.confidence:d}</Confidence>"
            "</DRI>"
        )

    def to_json(self) -> str:
        return json.dumps({
            "status": self.status,
            "cell": self.cell,
            "part": self.part,
            "confidence": self.confidence,
        })


@dataclass
class DRIBoard:
    mask: str
    count: int
    unknown: int

    @classmethod
    def from_compact(cls, message: str) -> "DRIBoard":
        message = message.strip()
        m = BOARD_RE.match(message)
        if not m:
            raise ValueError(f"Invalid DRI board message: {message!r}")
        return cls(
            mask=m.group("mask"),
            count=int(m.group("count")),
            unknown=int(m.group("unknown")),
        )

    def to_abb(self) -> str:
        return f"B;{self.mask};{self.count:02d};{self.unknown:02d}"

    def to_kuka_line(self) -> str:
        return f"BOARD,{self.mask},{self.count:d},{self.unknown:d}"

    def to_kuka_xml(self) -> str:
        return (
            "<DRI_BOARD>"
            f"<Mask>{self.mask}</Mask>"
            f"<Count>{self.count:d}</Count>"
            f"<Unknown>{self.unknown:d}</Unknown>"
            "</DRI_BOARD>"
        )

    def to_json(self) -> str:
        return json.dumps({
            "mask": self.mask,
            "count": self.count,
            "unknown": self.unknown,
        })


class DRIClient:
    def __init__(self, host: str, port: int, timeout: float = 2.0, persistent: bool = False):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.persistent = persistent
        self.sock: Optional[socket.socket] = None
        self.lock = threading.Lock()

    def close(self):
        with self.lock:
            if self.sock is not None:
                try:
                    self.sock.close()
                finally:
                    self.sock = None

    def _connect(self) -> socket.socket:
        if self.persistent and self.sock is not None:
            return self.sock

        sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        sock.settimeout(self.timeout)

        if self.persistent:
            self.sock = sock

        return sock

    def request(self, command: str) -> str:
        payload = command.strip().encode("ascii")

        with self.lock:
            sock = self._connect()

            try:
                sock.sendall(payload)
                data = sock.recv(8192)
                if not data:
                    raise ConnectionError("DRI server closed connection without response")
                return data.decode("utf-8", errors="ignore").strip()

            except Exception:
                if self.persistent:
                    self.close()
                raise

            finally:
                if not self.persistent:
                    sock.close()


def format_error(target_format: str, error_code: int = 9) -> str:
    target = DRITarget(status=error_code, cell=0, part=0, confidence=0)
    if target_format == "abb":
        return target.to_abb()
    if target_format == "kuka_xml":
        return target.to_kuka_xml()
    if target_format == "kuka_line":
        return target.to_kuka_line()
    if target_format == "json":
        return target.to_json()
    return target.to_abb()


def transform_target(message: str, target_format: str) -> str:
    target = DRITarget.from_compact(message)

    if target_format == "abb":
        return target.to_abb()
    if target_format == "kuka_xml":
        return target.to_kuka_xml()
    if target_format == "kuka_line":
        return target.to_kuka_line()
    if target_format == "json":
        return target.to_json()

    raise ValueError(f"Unknown target format: {target_format}")


def transform_board(message: str, target_format: str) -> str:
    board = DRIBoard.from_compact(message)

    if target_format == "abb":
        return board.to_abb()
    if target_format == "kuka_xml":
        return board.to_kuka_xml()
    if target_format == "kuka_line":
        return board.to_kuka_line()
    if target_format == "json":
        return board.to_json()

    raise ValueError(f"Unknown target format: {target_format}")


class RobotGateway:
    def __init__(
        self,
        dri_host: str,
        dri_port: int,
        listen_host: str,
        listen_port: int,
        target_format: str,
        timeout: float = 2.0,
        persistent_dri: bool = False,
        add_newline: bool = False,
    ):
        self.dri = DRIClient(dri_host, dri_port, timeout=timeout, persistent=persistent_dri)
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.target_format = target_format
        self.timeout = timeout
        self.add_newline = add_newline

    def _handle_command(self, command: str) -> str:
        command = command.strip().upper()

        if command in ("PING", "ALIVE"):
            if self.target_format == "kuka_xml":
                return "<DRI><Status>ALIVE</Status></DRI>"
            return "ALIVE"

        if command in ("GET_NEXT", "NEXT", "GET_TARGET"):
            raw = self.dri.request("GET_NEXT")
            return transform_target(raw, self.target_format)

        if command in ("GET_BOARD", "BOARD"):
            raw = self.dri.request("GET_BOARD")
            return transform_board(raw, self.target_format)

        if command in ("QUIT", "CLOSE"):
            return "CLOSE"

        return format_error(self.target_format)

    def serve_forever(self):
        print(f"Robot gateway listening on {self.listen_host}:{self.listen_port}")
        print(f"DRI source: {self.dri.host}:{self.dri.port}")
        print(f"Robot output format: {self.target_format}")

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind((self.listen_host, self.listen_port))
            srv.listen(10)

            while True:
                conn, addr = srv.accept()
                threading.Thread(target=self._client_thread, args=(conn, addr), daemon=True).start()

    def _client_thread(self, conn: socket.socket, addr):
        print(f"Robot connected: {addr}")

        with conn:
            conn.settimeout(self.timeout)

            while True:
                try:
                    data = conn.recv(1024)
                    if not data:
                        return

                    command = data.decode("utf-8", errors="ignore").strip()
                    if not command:
                        continue

                    try:
                        response = self._handle_command(command)
                    except Exception as exc:
                        print(f"Gateway error for command {command!r}: {exc}")
                        response = format_error(self.target_format)

                    if self.add_newline:
                        response += "\n"

                    conn.sendall(response.encode("utf-8"))

                    if command.upper() in ("QUIT", "CLOSE"):
                        return

                except socket.timeout:
                    continue
                except Exception as exc:
                    print(f"Robot connection closed/error: {addr}: {exc}")
                    return


def request_once(args):
    client = DRIClient(args.dri_host, args.dri_port, timeout=args.timeout, persistent=False)
    command = "GET_BOARD" if args.command == "board" else "GET_NEXT"
    raw = client.request(command)

    if args.command == "board":
        print(transform_board(raw, args.format))
    else:
        print(transform_target(raw, args.format))


def serve(args):
    gateway = RobotGateway(
        dri_host=args.dri_host,
        dri_port=args.dri_port,
        listen_host=args.listen_host,
        listen_port=args.listen_port,
        target_format=args.format,
        timeout=args.timeout,
        persistent_dri=args.persistent_dri,
        add_newline=args.newline,
    )
    gateway.serve_forever()


def main():
    parser = argparse.ArgumentParser(description="DRI robot adapter gateway for ABB and KUKA robots.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    common_format = ("abb", "kuka_xml", "kuka_line", "json")

    p = sub.add_parser("serve")
    p.add_argument("--dri-host", default="127.0.0.1")
    p.add_argument("--dri-port", type=int, default=5005)
    p.add_argument("--listen-host", default="0.0.0.0")
    p.add_argument("--listen-port", type=int, default=6100)
    p.add_argument("--format", choices=common_format, required=True)
    p.add_argument("--timeout", type=float, default=2.0)
    p.add_argument("--persistent-dri", action="store_true")
    p.add_argument("--newline", action="store_true")
    p.set_defaults(func=serve)

    p = sub.add_parser("once")
    p.add_argument("--dri-host", default="127.0.0.1")
    p.add_argument("--dri-port", type=int, default=5005)
    p.add_argument("--format", choices=common_format, required=True)
    p.add_argument("--command", choices=("next", "board"), default="next")
    p.add_argument("--timeout", type=float, default=2.0)
    p.set_defaults(func=request_once)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
