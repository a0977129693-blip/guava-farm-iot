const express = require('express');
const cors = require('cors');
const admin = require('firebase-admin');

const app = express();
app.use(cors());
app.use(express.json());

// =======================================================
// !!! 重要：請替換成你的 Firebase 服務帳戶憑證 (Service Account) !!!
// =======================================================
const serviceAccount = {
  type: "service_account",
  project_id: "your-guava-farm",
  privateKey: "-----BEGIN PRIVATE KEY-----\nYOUR_PRIVATE_KEY_HERE\n-----END PRIVATE KEY-----\n",
  clientEmail: "firebase-adminsdk-xxxxx@your-guava-farm.iam.gserviceaccount.com",
};

admin.initializeApp({
  credential: admin.credential.cert(serviceAccount),
  databaseURL: "https://your-guava-farm-default-rtdb.firebaseio.com" // 替換為你的 RTDB URL
});

const db = admin.database();

// 接收 Wokwi 資料的 API 節點
app.post('/api/data', async (req, res) => {
  try {
    const telemetry = req.body;
    
    // 加上後端伺服器的精準時間戳
    const timestamp = Date.now();
    const dataWithTime = {
      ...telemetry,
      createdAt: timestamp
    };

    // 1. 更新最新即時狀態 (給儀表板即時刷新)
    await db.ref('orchard_data/current').set(dataWithTime);

    // 2. 推播至歷史資料庫 (給前端繪製歷史曲線圖)
    await db.ref('orchard_data/history').push(dataWithTime);

    // 3. 限制歷史紀錄總數，避免免費額度爆滿 (只保留最新的 50 筆)
    const historyRef = db.ref('orchard_data/history');
    const snapshot = await historyRef.once('value');
    if (snapshot.exists() && Object.keys(snapshot.val()).length > 50) {
      const keys = Object.keys(snapshot.val());
      // 刪除最舊的一筆
      await historyRef.child(keys[0]).remove();
    }

    console.log("✅ 資料已成功同步至 Firebase:", dataWithTime);
    res.status(200).json({ status: "success", message: "Data synced to Firebase" });
  } catch (error) {
    console.error("❌ 後端處理失敗:", error);
    res.status(500).json({ status: "error", message: error.message });
  }
});

// 健康檢查節點
app.get('/', (req, res) => {
  res.send('Guava Farm IoT Backend is running.');
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`🚀 後端伺服器正運行於通訊埠 ${PORT}`);
});
