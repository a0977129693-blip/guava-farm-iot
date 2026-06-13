import machine
from machine import Pin, ADC, PWM
import dht
import time
import network
import ujson
import urequests
import _thread

# ================= 1. 硬體腳位初始化 =================
sensor_dht = dht.DHT22(Pin(15))
soil_sensor = ADC(Pin(34))
soil_sensor.atten(ADC.ATTN_11DB)
valve_servo = PWM(Pin(18), freq=50)

led_r = Pin(5, Pin.OUT)
led_g = Pin(4, Pin.OUT)
led_b = Pin(2, Pin.OUT)

trig_pin = Pin(16, Pin.OUT)
echo_pin = Pin(17, Pin.IN)

row_pins = [Pin(13, Pin.OUT), Pin(12, Pin.OUT), Pin(14, Pin.OUT), Pin(27, Pin.OUT)]
col_pins = [Pin(26, Pin.IN, Pin.PULL_DOWN), Pin(25, Pin.IN, Pin.PULL_DOWN), Pin(33, Pin.IN, Pin.PULL_DOWN), Pin(32, Pin.IN, Pin.PULL_DOWN)]
key_map = [['1', '2', '3', 'A'], ['4', '5', '6', 'B'], ['7', '8', '9', 'C'], ['*', '0', '#', 'D']]

# !!! 請替換為你部署在 Render 的後端網址 !!!
API_URL = "https://your-backend-name.onrender.com/api/data" 

# ================= 2. 系統狀態與變數 =================
system_mode = "AUTO"  
valve_is_open = False 
upload_pending = False
payload_to_upload = {}

# ================= 3. 輔助函式定義 =================
def background_upload_task():
    global upload_pending, payload_to_upload
    while True:
        if upload_pending:
            try:
                json_data = ujson.dumps(payload_to_upload)
                print(f" ☁️ [雲端同步] 正在傳送資料至 Render...")
                response = urequests.post(API_URL, headers={'Content-Type': 'application/json'}, data=json_data)
                print(f" └── ☁️ [雲端同步] 伺服器回應碼: {response.status_code}")
                response.close()
            except Exception as e:
                print(f" └── ⚠️ [雲端同步] 資料上傳失敗: {e}")
            upload_pending = False
        time.sleep(0.5)

def connect_wifi():
    print("🌐 準備連接 Wi-Fi...")
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect("Wokwi-GUEST", "")
    timeout = 10
    while not wlan.isconnected() and timeout > 0:
        set_led_color(1, 1, 1); time.sleep(0.5)
        set_led_color(0, 0, 0); time.sleep(0.5)
        timeout -= 1
    if wlan.isconnected():
        print("✅ Wi-Fi 連線成功！IP:", wlan.ifconfig()[0])
        return True
    return False

def set_led_color(r, g, b):
    led_r.value(r)
    led_g.value(g)
    led_b.value(b)

def operate_valve(open_valve):
    global valve_is_open
    if open_valve:
        valve_servo.duty(int(40 + (90 / 180) * 75))
        valve_is_open = True
    else:
        valve_servo.duty(int(40 + (0 / 180) * 75))
        valve_is_open = False

def scan_keypad():
    for row in range(4):
        row_pins[row].value(1)
        for col in range(4):
            if col_pins[col].value() == 1:
                row_pins[row].value(0)
                return key_map[row][col]
        row_pins[row].value(0)
    return None

def get_water_level():
    trig_pin.value(0); time.sleep_us(2)
    trig_pin.value(1); time.sleep_us(10); trig_pin.value(0)
    t = machine.time_pulse_us(echo_pin, 1, 30000)
    if t < 0: return -1, 0 
    distance_cm = (t * 0.0343) / 2
    if distance_cm >= 200.0: capacity = 0.0
    elif distance_cm <= 20.0: capacity = 100.0
    else: capacity = ((200.0 - distance_cm) / (200.0 - 20.0)) * 100
    return distance_cm, capacity

def get_led_status_text(temp, soil, water_cap):
    if system_mode == "MANUAL": return "MANUAL" # 對應前端狀態機
    if temp >= 35.0: return "EMERGENCY_LOCK"
    if soil < 30.0 and water_cap <= 5.0: return "EMERGENCY_LOCK"
    if soil < 30.0 and water_cap > 5.0: return "AUTO_DRIP"
    return "IDLE"

# ================= 4. 系統啟動 =================
print("智慧芭樂果園系統啟動中...")
operate_valve(False)
is_online = connect_wifi()
_thread.start_new_thread(background_upload_task, ())
last_upload_time = time.ticks_ms()

# ================= 5. 主程式無窮迴圈 =================
while True:
    pressed_key = scan_keypad()
    if pressed_key:
        print("\n>>> 📥 接收到鍵盤指令 <<<")
        if pressed_key == 'A' and system_mode != "AUTO":
            system_mode = "AUTO"
            print("🔄 執行：已切換成【自動模式 (AUTO)】")
        elif pressed_key == 'B' and system_mode != "MANUAL":
            system_mode = "MANUAL"
            print("🛠️ 執行：已切換成【手動模式 (MANUAL)】")
            set_led_color(1, 1, 1) 
        elif pressed_key == '1' and system_mode == "MANUAL":
            operate_valve(not valve_is_open)
            print(f"🚰 執行：手動強制將水閥 {'【開啟】' if valve_is_open else '【關閉】'}")
        elif pressed_key == 'C':
            print("📊 執行：系統狀態一切運作正常！")
        time.sleep(0.15) 
            
    current_time = time.ticks_ms()
    if time.ticks_diff(current_time, last_upload_time) > 5000:
        try:
            sensor_dht.measure()
            temp = sensor_dht.temperature()
            hum = sensor_dht.humidity()
            
            # Wokwi 模擬潛位器：為了符合常理，將 0-4095 轉換為土壤含水率 0%-100%
            soil_moisture = ((soil_sensor.read() / 4095.0) * 100)
            water_dist, water_capacity = get_water_level()
            
            # 自動模式 FSM 邏輯控制
            if system_mode == "AUTO":
                if temp >= 35.0:
                    set_led_color(1, 0, 0); operate_valve(False)
                elif soil_moisture < 30.0 and water_capacity > 5.0:
                    set_led_color(0, 0, 1); operate_valve(True)
                elif soil_moisture < 30.0 and water_capacity <= 5.0:
                    set_led_color(1, 0, 1); operate_valve(False)
                else:
                    set_led_color(0, 1, 0); operate_valve(False)
            
            # 取得系統當前 FSM 狀態名稱
            sys_state = get_led_status_text(temp, soil_moisture, water_capacity)
            
            # 特殊預警判定：若高溫高濕則觸發病害預警（配合前端功能）
            if sys_state == "IDLE" and temp >= 28.0 and hum >= 75.0:
                sys_state = "DISEASE_ALERT"
            
            print("\n" + "━"*45)
            print(f" 📡 【芭樂園即時戰情】 狀態：[{sys_state}]")
            print(f" 🌡️ 氣溫 {temp:.1f}°C | 濕度 {hum:.1f}% | 🌱 土壤水分 {soil_moisture:.1f}%")
            print(f" 🚰 水源容量 {water_capacity:.1f}% | 水閥 [{'🟢 開啟' if valve_is_open else '🔴 關閉'}]")
            print("━"*45)
            
            if is_online and not upload_pending:
                payload_to_upload = {
                    "mode": system_mode, 
                    "valve_status": valve_is_open,
                    "temperature": round(temp, 1), 
                    "humidity": round(hum, 1),
                    "soil_moisture": round(soil_moisture, 1), 
                    "water_capacity": round(water_capacity, 1),
                    "well_depth": round(water_dist, 1),
                    "system_state": sys_state
                }
                upload_pending = True 
                
        except OSError:
            print("\n❌ 警告：讀取感測器失敗，請檢查 Wokwi 線路！")
            
        last_upload_time = current_time 

    time.sleep(0.01)
