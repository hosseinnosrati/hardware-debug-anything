"""Embedded Protocol Analyzer and Panic Trace Diagnostic Engine.

Parses ESP-IDF Guru Meditation panics, ARM crash logs, and digital bus transactions
(I2C address NACK, SPI framing errors, and UART bit timing).
"""

from __future__ import annotations
import re
from typing import Dict, List, Optional, Any


class ProtocolAnalyzer:
    """Parses serial terminal dumps and digital bus logs to identify protocol-level faults."""

    @classmethod
    def decode_esp32_panic(cls, log_text: str) -> Dict[str, Any]:
        """Decode ESP32 / ESP-IDF Guru Meditation Panic dumps."""
        panic_pattern = r"Guru Meditation Error:\s*Core\s*(\d+)\s*panic'ed\s*\(([^)]+)\)"
        backtrace_pattern = r"Backtrace:\s*([0-9a-fA-FxX:\s]+)"

        panic_match = re.search(panic_pattern, log_text)
        bt_match = re.search(backtrace_pattern, log_text)

        core_id = panic_match.group(1) if panic_match else "0"
        panic_reason = panic_match.group(2) if panic_match else "Unknown Panic"

        backtrace_frames = []
        if bt_match:
            raw_bt = bt_match.group(1).strip()
            pairs = raw_bt.split()
            for pair in pairs:
                parts = pair.split(":")
                if len(parts) == 2:
                    backtrace_frames.append({"pc": parts[0], "sp": parts[1]})

        # Diagnostic explanation mapping
        explanations = {
            "LoadProhibited": "CPU attempted to read memory from an invalid or protected virtual address (often a NULL pointer dereference).",
            "StoreProhibited": "CPU attempted to write data to an invalid address or read-only Flash region.",
            "InstrFetchProhibited": "Instruction fetch attempted from non-executable memory (function pointer corruption).",
            "Unhandled debug exception": "A software breakpoint or watchpoint triggered without an attached JTAG debugger.",
            "Double exception vector": "An unhandled interrupt or fault occurred while servicing an existing exception.",
            "Interrupt wdt timeout": "Interrupt Service Routine (ISR) exceeded time budget without yielding to FreeRTOS.",
        }

        explanation = explanations.get(panic_reason, "Hardware execution exception trapped by Xtensa/RISC-V core.")

        return {
            "target": "ESP32 / ESP-IDF",
            "core_id": int(core_id),
            "panic_reason": panic_reason,
            "root_cause": explanation,
            "backtrace_frames": backtrace_frames,
            "suggested_action": "Check NULL pointer dereferences in call stack and verify task watchdog timeouts.",
        }

    @classmethod
    def analyze_i2c_bus_log(
        cls,
        address_hex: str,
        acknowledged: bool,
        bus_voltage: float = 3.3,
        clock_khz: float = 100.0,
    ) -> Dict[str, Any]:
        """Analyze I2C transaction status and diagnose physical/protocol failures."""
        addr_int = int(address_hex, 16) if isinstance(address_hex, str) else int(address_hex)
        is_ack = acknowledged

        if is_ack:
            return {
                "status": "PASS",
                "device_address": f"0x{addr_int:02X}",
                "summary": "Target peripheral acknowledged address phase.",
            }

        # Failure diagnosis for Address NACK
        diagnosis = [
            f"Device address 0x{addr_int:02X} returned NACK on 9th clock cycle.",
            "1. Address Mismatch: Check 7-bit vs 8-bit addressing format (e.g. shifted by 1 bit for R/W).",
            "2. Missing Pull-ups: I2C requires external pull-up resistors on SDA/SCL lines to VCC.",
            "3. Power State: Ensure the slave sensor is powered and out of RESET sleep mode.",
        ]

        # Recommended pull-up calculation based on bus capacitance and frequency
        rec_pullup = "4.7 kΩ" if clock_khz <= 100 else "2.2 kΩ"

        return {
            "status": "FAIL",
            "fault_type": "I2C Address NACK",
            "target_address": f"0x{addr_int:02X}",
            "diagnostic_steps": diagnosis,
            "recommended_pullup": rec_pullup,
            "bus_speed_khz": clock_khz,
        }

    @classmethod
    def estimate_uart_baud(cls, pulse_widths_us: List[float]) -> Dict[str, Any]:
        """Estimate baud rate from measured digital pulse widths on RX pin."""
        if not pulse_widths_us:
            return {"status": "FAIL", "reason": "No pulse timing samples provided."}

        min_pulse = min(pulse_widths_us)
        raw_baud = 1e6 / min_pulse

        standard_bauds = [9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600]
        matched_baud = min(standard_bauds, key=lambda b: abs(b - raw_baud))
        error_pct = ((raw_baud - matched_baud) / matched_baud) * 100.0

        return {
            "status": "SUCCESS",
            "detected_baud": matched_baud,
            "measured_bit_time_us": round(min_pulse, 2),
            "estimated_raw_baud": round(raw_baud, 1),
            "timing_error_percent": round(error_pct, 2),
        }

