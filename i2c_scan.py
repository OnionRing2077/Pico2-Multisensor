# เครื่องมือสแกนหาขาและ Address ของจอ OLED I2C บน Raspberry Pi Pico
from machine import Pin, I2C
import time

print("=" * 50)
print("  เครื่องมือตรวจสอบ I2C Scanner สำหรับ Raspberry Pi Pico")
print("=" * 50)

# รายการคู่ขา SDA / SCL ยอดนิยมบน Raspberry Pi Pico
pin_pairs = [
    {"bus": 0, "sda": 4, "scl": 5, "desc": "GP4 (Pin 6), GP5 (Pin 7) - [ค่าเริ่มต้นของโปรเจกต์]"},
    {"bus": 0, "sda": 0, "scl": 1, "desc": "GP0 (Pin 1), GP1 (Pin 2) - [ขาบนสุดฝั่งซ้าย]"},
    {"bus": 1, "sda": 2, "scl": 3, "desc": "GP2 (Pin 4), GP3 (Pin 5) - [I2C Bus 1]"},
    {"bus": 1, "sda": 6, "scl": 7, "desc": "GP6 (Pin 9), GP7 (Pin 10)"},
    {"bus": 0, "sda": 8, "scl": 9, "desc": "GP8 (Pin 11), GP9 (Pin 12)"},
    {"bus": 0, "sda": 16, "scl": 17, "desc": "GP16 (Pin 21), GP17 (Pin 22)"},
]

found_any = False

for pair in pin_pairs:
    bus_id = pair["bus"]
    sda_pin = pair["sda"]
    scl_pin = pair["scl"]
    desc = pair["desc"]
    
    try:
        # ใช้ความถี่ 100 kHz เพื่อความเสถียรสูงสุด
        i2c = I2C(bus_id, sda=Pin(sda_pin), scl=Pin(scl_pin), freq=100000)
        devices = i2c.scan()
        if devices:
            found_any = True
            print(f"\n>>> [พบอุปกรณ์ I2C!]")
            print(f"    - คู่ขา: SDA = GP{sda_pin}, SCL = GP{scl_pin} ({desc})")
            print(f"    - Bus ID: {bus_id}")
            for d in devices:
                hex_addr = hex(d)
                dev_type = " (ตรงกับจอ OLED SSD1306)" if hex_addr in ['0x3c', '0x3d'] else ""
                print(f"    - I2C Address: {hex_addr} (ฐานสิบ: {d}){dev_type}")
    except Exception as e:
        pass

if not found_any:
    print("\n[ผลการสแกน]: ไม่พบอุปกรณ์ I2C บนขาใดๆ เลย!")
    print("\nข้อแนะนำในการตรวจสอบฮาร์ดแวร์:")
    print("1. เช็กลำดับขาบนตัวจอ OLED: ระวัง VCC กับ GND สลับกัน (บางรุ่น GND-VCC บางรุ่น VCC-GND)")
    print("2. เช็กสาย SDA และ SCL: ลองสลับขากันระหว่าง SDA กับ SCL")
    print("3. เช็กไฟเลี้ยง: ลองย้ายสาย VCC ของจอไปต่อที่ขา VBUS (ขา 40 ไฟ 5V จาก USB)")
    print("4. เช็กความแน่นของสาย Jumper บน Breadboard")
else:
    print("\n[สำเร็จ] นำค่า GP ที่พบไปใส่ใน main.py ได้ทันทีครับ!")
print("=" * 50)
