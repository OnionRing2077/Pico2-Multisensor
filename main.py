"""
โครงการพัฒนาระบบวัดระยะทางด้วยเซนเซอร์จำลอง (HC-SR04 Simulation)
บอร์ด: Raspberry Pi Pico / Pico 2
อุปกรณ์:
  - OLED Display 0.96" I2C (SSD1306): SDA -> GP4, SCL -> GP5
  - LED Lamp: ขาบวกต่อ GP15 ผ่าน R 220 Ohm, ขาลบต่อ GND
  - Ultrasonic Sensor HC-SR04: จำลองค่าระยะทางผ่านซอฟต์แวร์
"""

from machine import Pin, I2C, SoftI2C
import time
import math
import random

# ไดรเวอร์จอ OLED แบบ Robust Standalone (ป้องกันปัญหา Errno 5 EIO และ Buffer ล้น)
import framebuf

class RobustSSD1306(framebuf.FrameBuffer):
    def __init__(self, width=128, height=64, i2c=None, addr=0x3C):
        self.width = width
        self.height = height
        self.i2c = i2c
        self.addr = addr
        self.pages = self.height // 8
        self.buffer = bytearray(self.pages * self.width)
        super().__init__(self.buffer, self.width, self.height, framebuf.MONO_VLSB)
        self.init_display()

    def write_cmd(self, *cmds):
        """ส่งชุดคำสั่งรวมใน Transaction เดียว (Prefix 0x00) ป้องกัน I2C NACK"""
        buf = bytearray([0x00]) + bytearray(cmds)
        self.i2c.writeto(self.addr, buf)

    def init_display(self):
        self.write_cmd(0xAE)                      # Display OFF
        self.write_cmd(0xD5, 0x80)                # Clock Divide
        self.write_cmd(0xA8, self.height - 1)     # Multiplex Ratio
        self.write_cmd(0xD3, 0x00)                # Display Offset
        self.write_cmd(0x40)                      # Start Line = 0
        self.write_cmd(0x8D, 0x14)                # Charge Pump 7.5V
        self.write_cmd(0x20, 0x00)                # Horizontal Addressing
        self.write_cmd(0xA1)                      # Segment Re-map
        self.write_cmd(0xC8)                      # COM Output Scan Direction
        self.write_cmd(0xDA, 0x02 if self.height == 32 else 0x12)
        self.write_cmd(0x81, 0xFF)                # Contrast Max
        self.write_cmd(0xD9, 0xF1)                # Pre-charge Period
        self.write_cmd(0xDB, 0x40)                # VCOMH Deselect
        self.write_cmd(0xA4)                      # Entire Display Resume
        self.write_cmd(0xA6)                      # Normal Display
        self.write_cmd(0xAF)                      # Display ON
        self.fill(0)
        self.show()

    def show(self):
        self.write_cmd(0x21, 0x00, self.width - 1)
        self.write_cmd(0x22, 0x00, self.pages - 1)
        for page in range(self.pages):
            start = page * self.width
            self.i2c.writeto(self.addr, b'\x40' + self.buffer[start:start + self.width])

SSD1306_I2C = RobustSSD1306

# ==========================================
# 1. การกำหนดขาและโหมดการทำงาน (Configuration)
# ==========================================
USE_SIMULATION = True  # True = จำลองค่าเซนเซอร์, False = ใช้อุปกรณ์จริง

# ขาเชื่อมต่อ OLED I2C (I2C Controller 0)
I2C_SDA_PIN = 4
I2C_SCL_PIN = 5
I2C_FREQ = 100000  # ใช้ 100 kHz เพื่อความเสถียรของสัญญาณบน Breadboard
OLED_WIDTH = 128
OLED_HEIGHT = 64

# ขาเชื่อมต่อ LED
LED_PIN = 15

# ขาเชื่อมต่อ HC-SR04 (กรณีใช้งานจริง)
TRIG_PIN = 2
ECHO_PIN = 3

# เกณฑ์ระยะทางในการแจ้งเตือน (หน่วยเป็นเซนติเมตร)
THRESHOLD_DANGER = 10.0   # ต่ำกว่า 10 cm = อันตราย (ใกล้เกินไป)
THRESHOLD_WARNING = 30.0  # 10 - 30 cm = เตือนระวัง

# ==========================================
# 2. คลาสจำลองเซนเซอร์ HC-SR04 (Simulation Engine)
# ==========================================
class UltrasonicSimulator:
    """จำลองการอ่านค่าระยะทางของเซนเซอร์ HC-SR04 ให้มีการเคลื่อนที่เข้า-ออกอย่างสมจริง"""
    def __init__(self, min_dist=4.0, max_dist=85.0, cycle_speed=0.25):
        self.min_dist = min_dist
        self.max_dist = max_dist
        self.cycle_speed = cycle_speed
        self.step = 0.0

    def get_distance(self):
        # สร้างสัญญาณ Sine wave จำลองการเคลื่อนไหวของวัตถุ
        self.step += self.cycle_speed
        center = (self.max_dist + self.min_dist) / 2.0
        amplitude = (self.max_dist - self.min_dist) / 2.0
        
        # คลื่นหลัก + สัญญาณรบกวนเล็กน้อย (Jitter/Noise)
        noise = random.uniform(-0.6, 0.6)
        dist = center + amplitude * math.sin(self.step) + noise
        
        # ปรับค่าให้อยู่ในช่วงที่กำหนด
        dist = max(self.min_dist, min(self.max_dist, dist))
        return round(dist, 1)

# ==========================================
# 3. คลาสอ่านค่าจาก HC-SR04 ฮาร์ดแวร์จริง
# ==========================================
class UltrasonicReal:
    """สำหรับสลับมาใช้งานเซนเซอร์จริง HC-SR04 โดยวัดความกว้างสัญญาณพัลส์"""
    def __init__(self, trig_pin=TRIG_PIN, echo_pin=ECHO_PIN):
        self.trig = Pin(trig_pin, Pin.OUT)
        self.echo = Pin(echo_pin, Pin.IN)
        self.trig.value(0)
        time.sleep_ms(50)

    def get_distance(self):
        # ส่งสัญญาณ Trigger พัลส์ 10 ไมโครวินาที
        self.trig.value(0)
        time.sleep_us(2)
        self.trig.value(1)
        time.sleep_us(10)
        self.trig.value(0)

        # รอสัญญาณ Echo ขาขึ้น
        timeout = 30000  # ป้องกัน Loop ค้าง
        start_time = time.ticks_us()
        while self.echo.value() == 0:
            if time.ticks_diff(time.ticks_us(), start_time) > timeout:
                return -1.0  # Timeout

        echo_start = time.ticks_us()
        while self.echo.value() == 1:
            if time.ticks_diff(time.ticks_us(), echo_start) > timeout:
                return -1.0

        echo_end = time.ticks_us()
        duration = time.ticks_diff(echo_end, echo_start)
        
        # คำนวณระยะทางจากความเร็วเสียง (343 m/s = 0.0343 cm/us)
        # ระยะทาง = (เวลา * 0.0343) / 2
        distance = (duration * 0.0343) / 2.0
        return round(distance, 1)

# ==========================================
# 4. ฟังก์ชันค้นหาและเชื่อมต่อ I2C อัตโนมัติ (Smart I2C Auto-Detect)
# ==========================================
def get_i2c_connection():
    """ตรวจสอบการเชื่อมต่อ I2C โดยทดสอบทั้ง SoftI2C และ Hardware I2C พร้อม Handshake"""
    # ลำดับการทดสอบ: ให้ความสำคัญกับ SoftI2C ก่อนเพื่อป้องกันบั๊ก RP2040 Silicon Errata EIO
    methods = [
        ("SoftI2C (GP4/GP5 100kHz)", SoftI2C(sda=Pin(I2C_SDA_PIN), scl=Pin(I2C_SCL_PIN), freq=100000)),
        ("SoftI2C (GP4/GP5 50kHz)", SoftI2C(sda=Pin(I2C_SDA_PIN), scl=Pin(I2C_SCL_PIN), freq=50000)),
        ("Hardware I2C0 100kHz", I2C(0, sda=Pin(I2C_SDA_PIN, Pin.IN, Pin.PULL_UP), scl=Pin(I2C_SCL_PIN, Pin.IN, Pin.PULL_UP), freq=100000)),
    ]
    
    print("[I2C] กำลังทดสอบและเชื่อมต่อจอ OLED...")
    for desc, bus in methods:
        try:
            devices = bus.scan()
            if 0x3C in devices or 0x3D in devices:
                addr = 0x3C if 0x3C in devices else 0x3D
                # ทดสอบ Handshake คำสั่งเบื้องต้น
                bus.writeto(addr, bytearray([0x00, 0xAE]))
                print(f"[I2C สำเร็จ!] เชื่อมต่อจอสำเร็จผ่าน {desc} (Addr: {hex(addr)})")
                return bus, devices
        except Exception:
            pass

    # หากยังไม่ผ่าน ลองค้นหาคู่อื่นๆ
    candidates = [
        (0, 0, 1, "GP0 / GP1"),
        (1, 2, 3, "GP2 / GP3"),
    ]
    for bus_id, sda, scl, desc in candidates:
        try:
            bus = SoftI2C(sda=Pin(sda), scl=Pin(scl), freq=100000)
            devs = bus.scan()
            if 0x3C in devs or 0x3D in devs:
                addr = 0x3C if 0x3C in devs else 0x3D
                bus.writeto(addr, bytearray([0x00, 0xAE]))
                print(f"[I2C สำเร็จ!] ตรวจพบจอที่ขา {desc}")
                return bus, devs
        except Exception:
            pass

    # Fallback
    return SoftI2C(sda=Pin(I2C_SDA_PIN), scl=Pin(I2C_SCL_PIN), freq=50000), []

# ==========================================
# 5. คลาสควบคุมหน้าจอ OLED (Display Controller)
# ==========================================
class OLEDDisplayController:
    def __init__(self, i2c, devices, width=128, height=64):
        self.oled = None
        self.width = width
        self.height = height
        try:
            if devices:
                addr = 0x3C if 0x3C in devices else devices[0]
                self.oled = SSD1306_I2C(width, height, i2c, addr=addr)
                self.show_welcome()
            else:
                print("\n" + "!" * 50)
                print("[ข้อผิดพลาด] ไม่พบจอ OLED บนบอร์ด!")
                print("คำแนะนำในการแก้ไข:")
                print("1. เช็กลำดับขาบนตัวจอ OLED: ระวัง VCC กับ GND สลับกัน (บางรุ่น GND-VCC, บางรุ่น VCC-GND)")
                print("2. ลองย้ายสาย VCC ของจอไปต่อที่ขา VBUS (ขา 40 ไฟ 5V จาก USB)")
                print("3. ลองสลับสาย SDA กับ SCL")
                print("4. เช็กสาย Jumper ว่าแน่นหนาดีหรือไม่")
                print("!" * 50 + "\n")
        except Exception as e:
            print(f"[ERROR] ไม่สามารถเริ่มต้นหน้าจอ OLED ได้: {e}")

    def show_welcome(self):
        if not self.oled:
            return
        self.oled.fill(0)
        self.oled.text("=== DISTANCE ===", 0, 8)
        self.oled.text(" SENSOR SYSTEM  ", 0, 24)
        self.oled.text("Raspberry Pi Pico", 0, 40)
        self.oled.text("Initializing...", 0, 52)
        self.oled.show()
        time.sleep(1.5)

    def update_screen(self, distance, status, is_sim=True):
        if not self.oled:
            return
        self.oled.fill(0)
        
        # บรรทัดที่ 1: หัวข้อ + โหมด
        mode_label = "[SIM]" if is_sim else "[REAL]"
        self.oled.text(f"DIST MON {mode_label}", 0, 2)
        self.oled.hline(0, 12, self.width, 1)
        
        # บรรทัดที่ 2: แสดงค่าระยะทาง
        self.oled.text(f"Dist: {distance:5.1f} cm", 0, 18)
        
        # บรรทัดที่ 3: สถานะความปลอดภัย
        self.oled.text(f"Zone: {status}", 0, 32)
        
        # บรรทัดที่ 4: แถบกราฟิกวัดระยะทาง (Distance Progress Bar)
        # สเกล 0 - 80 cm
        bar_x = 0
        bar_y = 48
        bar_w = 126
        bar_h = 12
        self.oled.rect(bar_x, bar_y, bar_w, bar_h, 1)
        
        max_scale = 80.0
        fill_ratio = min(max(distance / max_scale, 0.0), 1.0)
        fill_width = int(fill_ratio * (bar_w - 4))
        if fill_width > 0:
            self.oled.fill_rect(bar_x + 2, bar_y + 2, fill_width, bar_h - 4, 1)
            
        self.oled.show()

# ==========================================
# 5. ฟังก์ชันหลัก (Main Program Routine)
# ==========================================
def main():
    print("=" * 45)
    print("  Raspberry Pi Pico: ระบบวัดระยะทางจำลอง")
    print(f"  โหมดการทำงาน: {'SIMULATION (จำลอง)' if USE_SIMULATION else 'HARDWARE จริง'}")
    print("=" * 45)

    # 1. ตั้งค่า LED
    led = Pin(LED_PIN, Pin.OUT)
    led.value(0)

    # 2. ตั้งค่าบัส I2C สำหรับจอ OLED (พร้อมระบบ Auto-Detect ขาและ Address)
    i2c, i2c_devices = get_i2c_connection()
    display = OLEDDisplayController(i2c, i2c_devices, OLED_WIDTH, OLED_HEIGHT)

    # 3. เตรียมอินสแตนซ์ของเซนเซอร์
    if USE_SIMULATION:
        sensor = UltrasonicSimulator(min_dist=3.5, max_dist=80.0, cycle_speed=0.2)
    else:
        sensor = UltrasonicReal(TRIG_PIN, ECHO_PIN)

    # ตัวแปรควบคุมจังหวะการกะพริบของ LED โดยไม่ block การทำงานหลัก
    last_toggle_time = time.ticks_ms()
    led_state = 0

    try:
        while True:
            # 1. อ่านค่าระยะทาง
            distance = sensor.get_distance()
            current_time = time.ticks_ms()

            # 2. ตรวจสอบเงื่อนไขระยะทางและควบคุม LED
            if distance < 0:
                status = "ERROR"
                led.value(0)
            elif distance < THRESHOLD_DANGER:
                # อันตราย (< 10 cm): กะพริบถี่มาก (ทุกๆ 100 ms) หรือติดค้าง
                status = "DANGER!"
                if time.ticks_diff(current_time, last_toggle_time) >= 100:
                    led_state = 1 - led_state
                    led.value(led_state)
                    last_toggle_time = current_time
            elif distance <= THRESHOLD_WARNING:
                # เตือนระวัง (10 - 30 cm): กะพริบเป็นจังหวะปานกลาง (ทุกๆ 400 ms)
                status = "WARNING"
                if time.ticks_diff(current_time, last_toggle_time) >= 400:
                    led_state = 1 - led_state
                    led.value(led_state)
                    last_toggle_time = current_time
            else:
                # ปลอดภัย (> 30 cm): ไฟ LED ดับ
                status = "SAFE"
                led.value(0)

            # 3. อัปเดตข้อมูลบนหน้าจอ OLED
            display.update_screen(distance, status, is_sim=USE_SIMULATION)

            # 4. พิมพ์รายงานลง Serial Console (Thonny REPL)
            led_report = "BLINK" if (status in ["DANGER!", "WARNING"]) else "OFF"
            print(f"[STATUS] ระยะทาง: {distance:5.1f} cm | โซน: {status:<8} | LED: {led_report}")

            # หน่วงเวลาสั้นๆ ก่อนรอบถัดไป
            time.sleep_ms(80)

    except KeyboardInterrupt:
        # หยุดโปรแกรมอย่างนุ่มนวลเมื่อกด Ctrl+C
        print("\n[INFO] สิ้นสุดการทำงานของโปรแกรม")
        led.value(0)
        if display.oled:
            display.oled.fill(0)
            display.oled.text("PROGRAM STOPPED", 4, 28)
            display.oled.show()

if __name__ == "__main__":
    main()
