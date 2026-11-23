"""Unit Tests for Hardware Debug Anything (HDA)."""

import unittest
from hda.debugger.gdb import ArmFaultDecoder
from hda.analyzer.protocol import ProtocolAnalyzer
from hda.simulation.renode import VirtualSiliconRunner


class TestArmFaultDecoder(unittest.TestCase):
    def test_precise_busfault(self):
        # CFSR: BFSR_PRECISERR (bit 9) | BFSR_BFARVALID (bit 15) -> 0x00008200
        diag = ArmFaultDecoder.decode_cfsr(
            cfsr_val=0x00008200,
            hfsr_val=0x40000000,
            bfar_val=0x20001004,
            pc_val=0x08001234,
        )
        self.assertEqual(diag.fault_type, "BusFault (Precise)")
        self.assertEqual(diag.fault_address, "0x20001004")
        self.assertEqual(diag.pc_address, "0x08001234")
        self.assertIn("peripheral", diag.cause_summary)

    def test_divbyzero_usagefault(self):
        # CFSR: UFSR_DIVBYZERO (bit 25) -> 0x02000000
        diag = ArmFaultDecoder.decode_cfsr(cfsr_val=0x02000000)
        self.assertEqual(diag.fault_type, "UsageFault (DIVBYZERO)")
        self.assertIn("zero", diag.cause_summary)

    def test_unaligned_usagefault(self):
        # CFSR: UFSR_UNALIGNED (bit 24) -> 0x01000000
        diag = ArmFaultDecoder.decode_cfsr(cfsr_val=0x01000000)
        self.assertEqual(diag.fault_type, "UsageFault (UNALIGNED)")


class TestProtocolAnalyzer(unittest.TestCase):
    def test_esp32_guru_panic(self):
        sample_log = """
        Guru Meditation Error: Core 0 panic'ed (LoadProhibited). Exception was unhandled.
        Backtrace: 0x40081234:0x3ffb0000 0x40085678:0x3ffb0020
        """
        res = ProtocolAnalyzer.decode_esp32_panic(sample_log)
        self.assertEqual(res["target"], "ESP32 / ESP-IDF")
        self.assertEqual(res["panic_reason"], "LoadProhibited")
        self.assertEqual(len(res["backtrace_frames"]), 2)
        self.assertIn("NULL pointer", res["root_cause"])

    def test_i2c_nack_diagnosis(self):
        res = ProtocolAnalyzer.analyze_i2c_bus_log("0x68", acknowledged=False, clock_khz=400.0)
        self.assertEqual(res["status"], "FAIL")
        self.assertEqual(res["fault_type"], "I2C Address NACK")
        self.assertEqual(res["recommended_pullup"], "2.2 kΩ")

    def test_uart_baud_detection(self):
        # 115200 baud bit time ~= 8.68 us
        pulses = [8.7, 17.4, 8.65, 26.1]
        res = ProtocolAnalyzer.estimate_uart_baud(pulses)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["detected_baud"], 115200)


class TestVirtualSilicon(unittest.TestCase):
    def test_renode_script_gen(self):
        resc = VirtualSiliconRunner.generate_renode_script("firmware.elf", board="stm32f103")
        self.assertIn("sysbus LoadELF", resc)
        self.assertIn("stm32f103c8", resc)

    def test_vector_table_inspection(self):
        # Valid ARM vector table: MSP=0x20005000, Reset=0x08000101 (Thumb bit 0 set)
        import struct
        fake_vector = struct.pack("<4I", 0x20005000, 0x08000101, 0x08000141, 0x08000161)
        res = VirtualSiliconRunner.inspect_arm_vector_table(fake_vector)
        self.assertEqual(res["integrity"], "PASS")
        self.assertTrue(res["thumb_mode_set"])


if __name__ == "__main__":
    unittest.main()

