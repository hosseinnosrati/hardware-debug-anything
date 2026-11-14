"""Silicon Fault Register Decoder and GDB-MI Diagnostic Engine.

Decodes ARM Cortex-M Configurable Fault Status Registers (CFSR, HFSR, BFAR, MMFAR)
and translates raw hardware crash dumps into actionable root-cause engineering explanations.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class FaultDiagnosis:
    fault_type: str
    severity: str
    cause_summary: str
    details: List[str]
    fault_address: Optional[str] = None
    pc_address: Optional[str] = None
    suggested_fix: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fault_type": self.fault_type,
            "severity": self.severity,
            "cause_summary": self.cause_summary,
            "fault_address": self.fault_address,
            "pc_address": self.pc_address,
            "details": self.details,
            "suggested_fix": self.suggested_fix,
        }


class ArmFaultDecoder:
    """Decodes ARM Cortex-M3/M4/M7/M33 architectural hardware faults."""

    # CFSR Bitmask Definitions (ARM v7-M / v8-M Architecture Reference Manual)
    # MemManage Fault Status Register (MMFSR: bits 0-7)
    MMFSR_IACCVIOL = 1 << 0
    MMFSR_DACCVIOL = 1 << 1
    MMFSR_MUNSTKERR = 1 << 3
    MMFSR_MSTKERR = 1 << 4
    MMFSR_MMARVALID = 1 << 7

    # BusFault Status Register (BFSR: bits 8-15)
    BFSR_IBUSERR = 1 << 8
    BFSR_PRECISERR = 1 << 9
    BFSR_IMPRECISERR = 1 << 10
    BFSR_UNSTKERR = 1 << 11
    BFSR_STKERR = 1 << 12
    BFSR_BFARVALID = 1 << 15

    # UsageFault Status Register (UFSR: bits 16-31)
    UFSR_UNDEFINSTR = 1 << 16
    UFSR_INVSTATE = 1 << 17
    UFSR_INVPC = 1 << 18
    UFSR_NOCP = 1 << 19
    UFSR_UNALIGNED = 1 << 24
    UFSR_DIVBYZERO = 1 << 25

    # HardFault Status Register (HFSR)
    HFSR_VECTTBL = 1 << 1
    HFSR_FORCED = 1 << 30
    HFSR_DEBUGEVT = 1 << 31

    @classmethod
    def decode_cfsr(
        cls,
        cfsr_val: int,
        hfsr_val: Optional[int] = None,
        bfar_val: Optional[int] = None,
        mmfar_val: Optional[int] = None,
        pc_val: Optional[int] = None,
    ) -> FaultDiagnosis:
        """Decode ARM CFSR (0xE000ED28) and related fault address registers."""
        details = []
        fault_type = "HardFault"
        severity = "FATAL"
        cause = "Unknown hardware execution fault."
        fault_addr_str = None
        pc_str = f"0x{pc_val:08X}" if pc_val is not None else None
        fix = ""

        # Check MemManage Faults
        if cfsr_val & cls.MMFSR_IACCVIOL:
            details.append("MemManage: Instruction access violation (MPU execution prevented).")
            cause = "Attempted code execution from non-executable memory region (MPU violation)."
            fix = "Verify MPU configuration and stack boundary permissions."
        if cfsr_val & cls.MMFSR_DACCVIOL:
            details.append("MemManage: Data access violation (MPU permission fault).")
            cause = "Read/write attempted to restricted memory address."

        # Check BusFaults
        if cfsr_val & cls.BFSR_PRECISERR:
            details.append("BusFault: Precise data bus error (exact fault address available).")
            fault_type = "BusFault (Precise)"
            cause = "CPU attempted data load/store from an unmapped or invalid peripheral address."
            if cfsr_val & cls.BFSR_BFARVALID and bfar_val is not None:
                fault_addr_str = f"0x{bfar_val:08X}"
                details.append(f"BusFault Address (BFAR): {fault_addr_str}")
            fix = f"Check pointer initialization. Ensure peripheral clock is enabled before register access at {fault_addr_str or 'target'}."

        if cfsr_val & cls.BFSR_IMPRECISERR:
            details.append("BusFault: Imprecise data bus error (buffered write fault).")
            fault_type = "BusFault (Imprecise)"
            cause = "Asynchronous write buffer error during background bus transaction."
            fix = "Insert a Data Synchronization Barrier (DSB) instruction to localize the fault."

        # Check UsageFaults
        if cfsr_val & cls.UFSR_DIVBYZERO:
            details.append("UsageFault: Integer division by zero trap.")
            fault_type = "UsageFault (DIVBYZERO)"
            cause = "Software executed SDIV or UDIV with divisor equal to zero."
            fix = "Add boundary checks prior to division operations."

        if cfsr_val & cls.UFSR_UNALIGNED:
            details.append("UsageFault: Unaligned memory access trap.")
            fault_type = "UsageFault (UNALIGNED)"
            cause = "Multi-byte load/store performed across non-aligned address boundary."
            fix = "Ensure struct packing uses '__attribute__((aligned(4)))' or avoid unaligned pointer casts."

        if cfsr_val & cls.UFSR_UNDEFINSTR:
            details.append("UsageFault: Undefined instruction executed.")
            fault_type = "UsageFault (UNDEFINSTR)"
            cause = "CPU attempted to decode an invalid opcode (possible firmware corruption or jump to wild pointer)."
            fix = "Inspect call stack and verify function pointer validity."

        # Check HardFault escalation
        if hfsr_val and (hfsr_val & cls.HFSR_FORCED):
            details.append("HardFault: FORCED escalation (a configurable fault escalated due to disabled handler).")

        return FaultDiagnosis(
            fault_type=fault_type,
            severity=severity,
            cause_summary=cause,
            details=details,
            fault_address=fault_addr_str,
            pc_address=pc_str,
            suggested_fix=fix or "Check stack alignment and peripheral initialization.",
        )
