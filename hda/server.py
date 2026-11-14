"""Hardware Debug Anything (HDA) FastMCP Server.

Exposes autonomous embedded systems debugging and diagnostic tools to AI agents:
- ARM Cortex-M HardFault & CFSR/BFAR root-cause analysis
- ESP32 Guru Meditation & panic backtrace decoding
- I2C / SPI / UART protocol error diagnosis
- Virtual Silicon Renode script synthesis & vector table inspection
"""

from __future__ import annotations
import sys
from typing import Dict, Any, List, Optional
from fastmcp import FastMCP

from hda.debugger.gdb import ArmFaultDecoder
from hda.analyzer.protocol import ProtocolAnalyzer
from hda.simulation.renode import VirtualSiliconRunner

mcp = FastMCP("Hardware-Debug-Anything")


@mcp.tool()
def decode_arm_hardfault(
    cfsr_hex: str,
    hfsr_hex: Optional[str] = None,
    bfar_hex: Optional[str] = None,
    pc_hex: Optional[str] = None,
) -> Dict[str, Any]:
    """Decode ARM Cortex-M CFSR/HFSR fault registers to find root cause of a HardFault.

    Args:
        cfsr_hex: Configurable Fault Status Register hex value (e.g. '0x00008200' or '8200').
        hfsr_hex: Optional HardFault Status Register hex value.
        bfar_hex: Optional BusFault Address Register hex value.
        pc_hex: Optional Program Counter register hex value when crash occurred.

    Returns:
        Structured diagnosis with fault type, exact cause, and suggested firmware fix.
    """
    cfsr_val = int(cfsr_hex, 16) if isinstance(cfsr_hex, str) else int(cfsr_hex)
    hfsr_val = int(hfsr_hex, 16) if hfsr_hex else None
    bfar_val = int(bfar_hex, 16) if bfar_hex else None
    pc_val = int(pc_hex, 16) if pc_hex else None

    diag = ArmFaultDecoder.decode_cfsr(
        cfsr_val=cfsr_val,
        hfsr_val=hfsr_val,
        bfar_val=bfar_val,
        pc_val=pc_val,
    )
    return diag.to_dict()


@mcp.tool()
def decode_esp32_panic_log(
    serial_log: str
) -> Dict[str, Any]:
    """Parse ESP32 / ESP-IDF serial terminal crash log to decode Guru Meditation panic and call stack.

    Args:
        serial_log: Raw serial terminal text containing 'Guru Meditation Error' and 'Backtrace:'.

    Returns:
        Decoded panic reason (e.g. LoadProhibited, WDT), core ID, and extracted call stack PC/SP frames.
    """
    return ProtocolAnalyzer.decode_esp32_panic(serial_log)


@mcp.tool()
def diagnose_i2c_bus_failure(
    address_hex: str,
    acknowledged: bool,
    clock_khz: float = 100.0,
) -> Dict[str, Any]:
    """Diagnose I2C communication failures, Address NACKs, and calculate recommended pull-up resistors.

    Args:
        address_hex: Peripheral 7-bit or 8-bit hex address (e.g. '0x68' for MPU6050, '0x3C' for SSD1306).
        acknowledged: True if slave ACK'd, False if NACK on 9th clock pulse.
        clock_khz: I2C bus clock speed in kHz (typically 100 or 400).

    Returns:
        Step-by-step diagnostic checklist, addressing mismatch checks, and pull-up recommendation.
    """
    return ProtocolAnalyzer.analyze_i2c_bus_log(
        address_hex=address_hex,
        acknowledged=acknowledged,
        clock_khz=clock_khz,
    )


@mcp.tool()
def estimate_uart_baud_rate(
    pulse_widths_us: List[float]
) -> Dict[str, Any]:
    """Auto-detect UART baud rate from logic analyzer pulse measurements on RX line.

    Args:
        pulse_widths_us: List of measured pulse durations in microseconds.

    Returns:
        Matched standard baud rate (e.g. 115200, 9600) and timing error percentage.
    """
    return ProtocolAnalyzer.estimate_uart_baud(pulse_widths_us)


@mcp.tool()
def verify_arm_vector_table(
    vector_hex_bytes: str
) -> Dict[str, Any]:
    """Inspect initial 16 bytes of ARM firmware binary to verify Reset Vector and Stack Pointer.

    Args:
        vector_hex_bytes: Hexadecimal string of first 16 bytes (e.g. '0050002041010008...').

    Returns:
        Initial Stack Pointer, Reset Handler address, Thumb mode verification, and integrity score.
    """
    raw_bytes = bytes.fromhex(vector_hex_bytes.replace(" ", "").replace("0x", ""))
    return VirtualSiliconRunner.inspect_arm_vector_table(raw_bytes)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
