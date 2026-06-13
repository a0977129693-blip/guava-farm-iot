const express = require('express');
const cors = require('cors');
const { createClient } = require('@supabase/supabase-js');

const app = express();
app.use(cors());
app.use(express.json());

// 🔐 安全性加密：從 Render 環境變數讀取 Supabase 憑證
const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_KEY = process.env.SUPABASE_KEY;

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY);

// 接收 Wokwi 資料的 API 節點
app.post('/api/data', async (req, res) => {
  try {
    const telemetry = req.body;

    // 將資料新增至 Supabase 中 (created_at 會由資料庫系統自動產生目前時間)
    const { data, error } = await supabase
      .from('orchard_data')
      .insert([
        {
          mode: telemetry.mode,
          valve_status: telemetry.valve_status,
          temperature: telemetry.temperature,
          humidity: telemetry.humidity,
          soil_moisture: telemetry.soil_moisture,
          water_capacity: telemetry.water_capacity,
          well_depth: telemetry.well_depth,
          system_state: telemetry.system_state
        }
      ]);

    if (error) throw error;

    console.log("✅ 資料已成功同步至 Supabase 資料庫");
    res.status(200).json({ status: "success" });
  } catch (error) {
    console.error("❌ Supabase 寫入失敗:", error.message);
    res.status(500).json({ status: "error", message: error.message });
  }
});

app.get('/', (req, res) => {
  res.send('Guava Farm IoT Backend is running securely with Supabase.');
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`🚀 後端伺服器正運行於通訊埠 ${PORT}`);
});
