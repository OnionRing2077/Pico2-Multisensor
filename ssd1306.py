# MicroPython SSD1306 OLED driver (I2C)
# ฉบับปรับปรุงแก้ไขปัญหา [Errno 5] EIO และรองรับทั้ง SSD1306 และชิปโคลน (SSD1315/SSD1306B)
import framebuf

# Register definitions
SET_CONTRAST = 0x81
SET_ENTIRE_ON = 0xA4
SET_NORM_INV = 0xA6
SET_DISP = 0xAE
SET_MEM_ADDR = 0x20
SET_COL_ADDR = 0x21
SET_PAGE_ADDR = 0x22
SET_DISP_START_LINE = 0x40
SET_SEG_REMAP = 0xA0
SET_MUX_RATIO = 0xA8
SET_COM_OUT_DIR = 0xC0
SET_DISP_OFFSET = 0xD3
SET_COM_PIN_CFG = 0xDA
SET_DISP_CLK_DIV = 0xD5
SET_PRECHARGE = 0xD9
SET_VCOM_DESEL = 0xDB
SET_CHARGE_PUMP = 0x8D

class SSD1306(framebuf.FrameBuffer):
    def __init__(self, width, height, external_vcc=False):
        self.width = width
        self.height = height
        self.external_vcc = external_vcc
        self.pages = self.height // 8
        self.buffer = bytearray(self.pages * self.width)
        super().__init__(self.buffer, self.width, self.height, framebuf.MONO_VLSB)
        self.init_display()

    def init_display(self):
        # รวมคำสั่งและพารามิเตอร์ส่งเป็นชุด ป้องกัน STOP condition คั่นกลางที่ทำให้เกิด [Errno 5] EIO
        self.write_cmd(SET_DISP)                                        # 0xAE Display OFF
        self.write_cmd(SET_DISP_CLK_DIV, 0x80)                          # 0xD5, 0x80 Clock Divide Ratio
        self.write_cmd(SET_MUX_RATIO, self.height - 1)                  # 0xA8, Multiplex Ratio
        self.write_cmd(SET_DISP_OFFSET, 0x00)                           # 0xD3, 0x00 Display Offset
        self.write_cmd(SET_DISP_START_LINE | 0x00)                      # 0x40 Start Line = 0
        self.write_cmd(SET_CHARGE_PUMP, 0x10 if self.external_vcc else 0x14) # 0x8D, 0x14 Charge Pump Enable
        self.write_cmd(SET_MEM_ADDR, 0x00)                              # 0x20, 0x00 Horizontal Mode
        self.write_cmd(SET_SEG_REMAP | 0x01)                            # 0xA1 Segment Re-map
        self.write_cmd(SET_COM_OUT_DIR | 0x08)                          # 0xC8 COM Output Scan
        self.write_cmd(SET_COM_PIN_CFG, 0x02 if self.height == 32 else 0x12) # 0xDA COM Pins Config
        self.write_cmd(SET_CONTRAST, 0xFF)                              # 0x81, 0xFF Contrast Max
        self.write_cmd(SET_PRECHARGE, 0x22 if self.external_vcc else 0xF1)   # 0xD9 Pre-charge
        self.write_cmd(SET_VCOM_DESEL, 0x40)                            # 0xDB VCOMH Deselect
        self.write_cmd(SET_ENTIRE_ON)                                   # 0xA4 Entire Display Resume
        self.write_cmd(SET_NORM_INV)                                    # 0xA6 Normal Display
        self.write_cmd(SET_DISP | 0x01)                                 # 0xAF Display ON
        self.fill(0)
        self.show()

    def poweroff(self):
        self.write_cmd(SET_DISP)

    def poweron(self):
        self.write_cmd(SET_DISP | 0x01)

    def contrast(self, contrast):
        self.write_cmd(SET_CONTRAST, contrast)

    def invert(self, invert):
        self.write_cmd(SET_NORM_INV | (invert & 1))

    def show(self):
        # ส่งพารามิเตอร์ขอบเขตคอลัมน์และเพจแบบครบชุดใน 1 คำสั่ง
        self.write_cmd(SET_COL_ADDR, 0, self.width - 1)
        self.write_cmd(SET_PAGE_ADDR, 0, self.pages - 1)
        self.write_data(self.buffer)

class SSD1306_I2C(SSD1306):
    def __init__(self, width, height, i2c, addr=0x3C, external_vcc=False):
        self.i2c = i2c
        self.addr = addr
        super().__init__(width, height, external_vcc)

    def write_cmd(self, *cmds):
        """ส่งชุดคำสั่งโดยใช้ Prefix 0x00 (Command Stream) ใน Transaction เดียว"""
        payload = bytearray([0x00]) + bytearray(cmds)
        self.i2c.writeto(self.addr, payload)

    def write_data(self, buf):
        """ส่งข้อมูลภาพทีละ Page (128 bytes) เพื่อความเสถียรสูงสุด ไม่ให้บัฟเฟอร์ล้น"""
        for page in range(self.pages):
            start = page * self.width
            chunk = buf[start : start + self.width]
            self.i2c.writeto(self.addr, b'\x40' + chunk)
