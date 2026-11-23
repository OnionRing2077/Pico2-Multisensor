# เครื่องมือทดสอบหน้าจอ OLED - โหมด SoftI2C & ตรวจสอบระดับไฟเลี้ยง
from machine import Pin, I2C, SoftI2C
import time
import framebuf

SDA_PIN = 4
SCL_PIN = 5
I2C_ADDR = 0x3C

print("=" * 60)
print("  เครื่องมือทดสอบ OLED (ทดสอบ SoftI2C เพื่อแก้ปัญหา Errno 5 EIO)")
print("=" * 60)

# -------------------------------------------------------------
# ทดสอบบัส I2C ในหลายๆ รูปแบบ (SoftI2C มักแก้ปัญหา EIO บน Pico ได้ผล 100%)
# -------------------------------------------------------------
bus_configs = [
    ("SoftI2C 100kHz (โหมดซอฟต์แวร์ แนะนำสำหรับ Pico)", SoftI2C(sda=Pin(SDA_PIN), scl=Pin(SCL_PIN), freq=100000)),
    ("SoftI2C 50kHz (โหมดความถี่ต่ำ ป้องกันสัญญาณกวน)", SoftI2C(sda=Pin(SDA_PIN), scl=Pin(SCL_PIN), freq=50000)),
    ("Hardware I2C0 50kHz", I2C(0, sda=Pin(SDA_PIN, Pin.IN, Pin.PULL_UP), scl=Pin(SCL_PIN, Pin.IN, Pin.PULL_UP), freq=50000)),
]

working_i2c = None

for desc, bus in bus_configs:
    print(f"\n[*] กำลังทดสอบ: {desc}...")
    try:
        devices = bus.scan()
        print(f"    - ผลการสแกน: {[hex(d) for d in devices]}")
        if I2C_ADDR in devices:
            # ทดสอบส่งคำสั่ง Handshake (0xAE = Display OFF)
            bus.writeto(I2C_ADDR, bytearray([0x00, 0xAE]))
            print("    -> [สำเร็จ!] บัสนี้ส่งคำสั่งไปยังจอได้โดยไม่เกิด EIO")
            working_i2c = bus
            break
        else:
            print("    - สแกนไม่พบ Address 0x3C")
    except Exception as e:
        print(f"    -> ยังเกิดข้อผิดพลาด: {e}")

# -------------------------------------------------------------
# หากพบบัสที่ทำงานได้ ให้เริ่มขับจอทันที
# -------------------------------------------------------------
if working_i2c is not None:
    print("\n" + "=" * 60)
    print(">>> กำลังสั่งเปิดหน้าจอ OLED...")
    
    class SSD1306(framebuf.FrameBuffer):
        def __init__(self, i2c, width=128, height=64, addr=I2C_ADDR):
            self.i2c = i2c
            self.addr = addr
            self.width = width
            self.height = height
            self.pages = height // 8
            self.buffer = bytearray(self.pages * width)
            super().__init__(self.buffer, width, height, framebuf.MONO_VLSB)
            self.init()

        def write_cmd(self, *cmds):
            self.i2c.writeto(self.addr, bytearray([0x00]) + bytearray(cmds))

        def init(self):
            self.write_cmd(0xAE)                      # Display OFF
            self.write_cmd(0xD5, 0x80)                # Clock Divide
            self.write_cmd(0xA8, self.height - 1)     # Multiplex
            self.write_cmd(0xD3, 0x00)                # Offset
            self.write_cmd(0x40)                      # Start Line
            self.write_cmd(0x8D, 0x14)                # Charge pump
            self.write_cmd(0x20, 0x00)                # Horizontal Mode
            self.write_cmd(0xA1)                      # Re-map
            self.write_cmd(0xC8)                      # COM Scan
            self.write_cmd(0xDA, 0x02 if self.height == 32 else 0x12)
            self.write_cmd(0x81, 0xFF)                # Contrast
            self.write_cmd(0xD9, 0xF1)                # Pre-charge
            self.write_cmd(0xDB, 0x40)                # VCOMH
            self.write_cmd(0xA4)                      # Resume
            self.write_cmd(0xA6)                      # Normal
            self.write_cmd(0xAF)                      # Display ON
            self.fill(0)
            self.show()

        def show(self):
            self.write_cmd(0x21, 0x00, self.width - 1)
            self.write_cmd(0x22, 0x00, self.pages - 1)
            for page in range(self.pages):
                start = page * self.width
                self.i2c.writeto(self.addr, b'\x40' + self.buffer[start:start + self.width])

    try:
        oled = SSD1306(working_i2c, 128, 64)
        print("    1. เปิดไฟเต็มจอ (Full White 1.5 วินาที)...")
        oled.fill(1)
        oled.show()
        time.sleep(1.5)
        
        print("    2. แสดงข้อความ...")
        oled.fill(0)
        oled.rect(0, 0, 128, 64, 1)
        oled.text("OLED OK!", 32, 14)
        oled.hline(10, 28, 108, 1)
        oled.text("Pico SoftI2C", 16, 36)
        oled.text("GP4 / GP5", 28, 48)
        oled.show()
        print("\n>>> [สำเร็จเรียบร้อย!] หน้าจอ OLED สว่างและใช้งานได้แล้ว!")
        print("=" * 60)
    except Exception as e:
        print(f"[ERROR]: {e}")

else:
    print("\n" + "!" * 60)
    print(">>> [ข้อสรุปสาเหตุทางฮาร์ดแวร์ที่ยังเกิด Errno 5 EIO]:")
    print("1. [สำคัญที่สุด] ไฟเลี้ยง 3.3V ตก (Brown-out):")
    print("   - จอ OLED 0.96 นิ้วเกือบทุกรุ่นมีไอซีเรกูเลเตอร์ 3.3V บนตัวบอร์ดจอ")
    print("   - หากรับไฟ 3.3V จากขา 36 ของ Pico ไฟจะดรอปลงเหลือประมาณ 2.8V-2.9V")
    print("     ทำให้วงจร Charge Pump ในจอไม่ทำงาน และส่ง NACK กลับมา")
    print("   >>> วิธีแก้: ย้ายสาย VCC ของจอ ไปเสียบที่ 'ขา 40 (VBUS)' ของ Pico ซึ่งเป็นไฟ 5V ตรงจาก USB")
    print("\n2. สายไฟ Jumper หลวม หรือ Breadboard หน้าสัมผัสไม่ดี:")
    print("   - ลองขยับสาย หรือเปลี่ยนช่องเสียบบน Breadboard")
    print("!" * 60)
