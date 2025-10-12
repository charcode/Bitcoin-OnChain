from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import ssl
import struct
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


def _read_varint(data: bytes, offset: int) -> tuple[int, int]:
    prefix = data[offset]
    offset += 1
    if prefix < 0xFD:
        return prefix, offset
    if prefix == 0xFD:
        value = struct.unpack_from("<H", data, offset)[0]
        offset += 2
        return value, offset
    if prefix == 0xFE:
        value = struct.unpack_from("<I", data, offset)[0]
        offset += 4
        return value, offset
    value = struct.unpack_from("<Q", data, offset)[0]
    offset += 8
    return value, offset


def _encode_varint(value: int) -> bytes:
    if value < 0xFD:
        return struct.pack("<B", value)
    if value <= 0xFFFF:
        return b"\xfd" + struct.pack("<H", value)
    if value <= 0xFFFFFFFF:
        return b"\xfe" + struct.pack("<I", value)
    return b"\xff" + struct.pack("<Q", value)


def _double_sha256(payload: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(payload).digest()).digest()


@dataclass
class ParsedTransaction:
    txid: str
    vin: List[dict]
    vout: List[dict]


class FulcrumClient:
    '''Minimal Electrum/Fulcrum JSON-RPC client for block retrieval.'''

    def __init__(
        self,
        host: str,
        port: int,
        use_ssl: bool = True,
        verify_ssl: bool = False,
        request_timeout: float = 30.0,
    ) -> None:
        self._host = host
        self._port = port
        self._use_ssl = use_ssl
        self._request_timeout = request_timeout
        self._id = 0
        self._ssl_context: Optional[ssl.SSLContext]
        if use_ssl:
            ctx = ssl.create_default_context()
            if not verify_ssl:
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
            self._ssl_context = ctx
        else:
            self._ssl_context = None

    async def aclose(self) -> None:
        # Stateless client; nothing to close.
        return None

    async def _request(self, method: str, params: Optional[list] = None) -> object:
        self._id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._id,
            "method": method,
            "params": params or [],
        }
        message = json.dumps(payload) + "\n"

        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(
                host=self._host,
                port=self._port,
                ssl=self._ssl_context,
            ),
            timeout=self._request_timeout,
        )
        try:
            writer.write(message.encode())
            await writer.drain()
            line = await asyncio.wait_for(reader.readline(), timeout=self._request_timeout)
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

        if not line:
            raise ConnectionError("Fulcrum returned no data")

        response = json.loads(line.decode())
        if response.get("error"):
            raise RuntimeError(response["error"])
        return response.get("result")

    async def get_block_hex(self, height: int) -> str:
        result = await self._request("blockchain.block.get_block", [height])
        if isinstance(result, dict):
            raw_hex = result.get("hex") or result.get("block")
        else:
            raw_hex = result
        if not isinstance(raw_hex, str):
            raise RuntimeError(f"Unexpected block payload from Fulcrum: {type(result)!r}")
        return raw_hex

    async def get_block_transactions(self, height: int) -> List[dict]:
        raw_hex = await self.get_block_hex(height)
        return [tx.__dict__ for tx in _parse_block(raw_hex)]


def _parse_block(raw_hex: str) -> List[ParsedTransaction]:
    data = bytes.fromhex(raw_hex)
    offset = 0
    if len(data) < 81:
        raise ValueError("Block data too short")
    offset += 80  # skip header
    tx_count, offset = _read_varint(data, offset)

    transactions: List[ParsedTransaction] = []
    for _ in range(tx_count):
        txid_serial = bytearray()
        vin_entries: List[dict] = []
        vout_entries: List[dict] = []

        version = struct.unpack_from("<I", data, offset)[0]
        txid_serial += struct.pack("<I", version)
        offset += 4

        has_witness = False
        if data[offset:offset + 2] == b"\x00\x01":
            has_witness = True
            offset += 2

        vin_count, offset = _read_varint(data, offset)
        txid_serial += _encode_varint(vin_count)

        for _ in range(vin_count):
            prev_hash = data[offset:offset + 32]
            offset += 32
            prev_index_bytes = data[offset:offset + 4]
            offset += 4
            script_len, offset = _read_varint(data, offset)
            script_sig = data[offset:offset + script_len]
            offset += script_len
            sequence = data[offset:offset + 4]
            offset += 4

            txid_serial += prev_hash
            txid_serial += prev_index_bytes
            txid_serial += _encode_varint(script_len)
            txid_serial += script_sig
            txid_serial += sequence

            prev_index = struct.unpack("<I", prev_index_bytes)[0]
            is_coinbase = prev_hash == b"\x00" * 32 and prev_index == 0xFFFFFFFF
            if is_coinbase:
                vin_entry = {
                    "coinbase": script_sig.hex(),
                    "txinwitness": [],
                }
            else:
                vin_entry = {
                    "txid": prev_hash[::-1].hex(),
                    "vout": prev_index,
                    "txinwitness": [],
                }
            vin_entries.append(vin_entry)

        vout_count, offset = _read_varint(data, offset)
        txid_serial += _encode_varint(vout_count)

        for _ in range(vout_count):
            value_sats = struct.unpack_from("<Q", data, offset)[0]
            offset += 8
            script_len, offset = _read_varint(data, offset)
            script_pubkey = data[offset:offset + script_len]
            offset += script_len

            txid_serial += struct.pack("<Q", value_sats)
            txid_serial += _encode_varint(script_len)
            txid_serial += script_pubkey

            script_type = "nulldata" if script_pubkey.startswith(b"\x6a") else "standard"
            vout_entries.append(
                {
                    "value": value_sats / 1e8,
                    "scriptPubKey": {"type": script_type},
                }
            )

        if has_witness:
            for vin_entry in vin_entries:
                stack_count, offset = _read_varint(data, offset)
                witness_items: List[str] = []
                for _ in range(stack_count):
                    item_len, offset = _read_varint(data, offset)
                    witness = data[offset:offset + item_len]
                    offset += item_len
                    witness_items.append(witness.hex())
                vin_entry["txinwitness"] = witness_items
        else:
            for vin_entry in vin_entries:
                vin_entry.setdefault("txinwitness", [])

        locktime = data[offset:offset + 4]
        offset += 4
        txid_serial += locktime

        txid = _double_sha256(bytes(txid_serial))[::-1].hex()

        transactions.append(
            ParsedTransaction(
                txid=txid,
                vin=vin_entries,
                vout=vout_entries,
            )
        )

    return transactions
